"""IdP group synchronization for dynamic provider-managed memberships."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ade_api.common.time import utc_now
from ade_api.core.security.hashing import hash_password
from ade_api.core.security.tokens import mint_opaque_token
from ade_api.settings import Settings
from ade_db.models import Group, GroupMembership, GroupMembershipMode, GroupSource, User

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized or "group"


@dataclass(frozen=True, slots=True)
class ProviderUser:
    external_id: str
    email: str
    display_name: str | None


@dataclass(frozen=True, slots=True)
class ProviderGroup:
    external_id: str
    display_name: str
    description: str | None
    slug_hint: str | None
    dynamic: bool
    member_external_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GroupSyncStats:
    users_upserted: int
    groups_upserted: int
    memberships_added: int
    memberships_removed: int


class EntraGraphAdapter:
    """Microsoft Entra / Graph adapter for users, groups, and memberships."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._tenant_id = (settings.auth_group_sync_tenant_id or "").strip()
        self._client_id = (settings.auth_group_sync_client_id or "").strip()
        self._client_secret = (
            settings.auth_group_sync_client_secret.get_secret_value().strip()
            if settings.auth_group_sync_client_secret
            else ""
        )
        if not self._tenant_id or not self._client_id or not self._client_secret:
            raise RuntimeError(
                "Group sync is enabled but Entra credentials are missing "
                "(ADE_AUTH_GROUP_SYNC_TENANT_ID / CLIENT_ID / CLIENT_SECRET)."
            )

    def _access_token(self) -> str:
        token_url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(token_url, data=payload)
            response.raise_for_status()
            body = response.json()
        token = body.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError("Failed to mint Graph access token for group sync.")
        return token

    @staticmethod
    def _collect_pages(token: str, url: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {token}"}
        next_url = url
        with httpx.Client(timeout=30.0, headers=headers) as client:
            while next_url:
                response = client.get(next_url)
                response.raise_for_status()
                payload = response.json()
                page_items = payload.get("value")
                if isinstance(page_items, list):
                    for item in page_items:
                        if isinstance(item, dict):
                            records.append(item)
                next_link = payload.get("@odata.nextLink")
                next_url = next_link if isinstance(next_link, str) and next_link else ""
        return records

    def fetch_users(self) -> list[ProviderUser]:
        token = self._access_token()
        records = self._collect_pages(
            token,
            "https://graph.microsoft.com/v1.0/users"
            "?$select=id,mail,userPrincipalName,displayName",
        )
        users: list[ProviderUser] = []
        for record in records:
            external_id = str(record.get("id") or "").strip()
            mail = str(record.get("mail") or "").strip()
            user_principal_name = str(record.get("userPrincipalName") or "").strip()
            email = (mail or user_principal_name).lower()
            if not external_id or not email:
                continue
            display_name = str(record.get("displayName") or "").strip() or None
            users.append(
                ProviderUser(
                    external_id=external_id,
                    email=email,
                    display_name=display_name,
                )
            )
        return users

    def fetch_groups(self) -> list[ProviderGroup]:
        token = self._access_token()
        records = self._collect_pages(
            token,
            "https://graph.microsoft.com/v1.0/groups"
            "?$select=id,displayName,description,mailNickname,groupTypes,membershipRule",
        )
        groups: list[ProviderGroup] = []
        for record in records:
            external_id = str(record.get("id") or "").strip()
            display_name = str(record.get("displayName") or "").strip()
            if not external_id or not display_name:
                continue
            group_types = record.get("groupTypes")
            dynamic = False
            if isinstance(group_types, list):
                dynamic = any(str(item) == "DynamicMembership" for item in group_types)
            membership_rule = str(record.get("membershipRule") or "").strip()
            dynamic = dynamic or bool(membership_rule)
            members = self._collect_pages(
                token,
                f"https://graph.microsoft.com/v1.0/groups/{external_id}/members?$select=id",
            )
            member_ids = tuple(
                str(item.get("id") or "").strip()
                for item in members
                if str(item.get("id") or "").strip()
            )
            groups.append(
                ProviderGroup(
                    external_id=external_id,
                    display_name=display_name,
                    description=str(record.get("description") or "").strip() or None,
                    slug_hint=str(record.get("mailNickname") or "").strip() or None,
                    dynamic=dynamic,
                    member_external_ids=member_ids,
                )
            )
        return groups


class GroupSyncService:
    """Reconcile provider-managed groups and memberships into ADE tables."""

    def __init__(self, *, session: Session) -> None:
        self._session = session

    def run_once(self, *, settings: Settings) -> GroupSyncStats:
        provider = (settings.auth_group_sync_provider or "").strip().lower()
        if provider != "entra":
            raise RuntimeError(f"Unsupported group sync provider: {provider!r}")

        adapter = EntraGraphAdapter(settings=settings)
        provider_users = adapter.fetch_users()
        provider_groups = adapter.fetch_groups()
        logger.info(
            "sso.group_sync.fetch.complete",
            extra={
                "provider": provider,
                "users": len(provider_users),
                "groups": len(provider_groups),
            },
        )

        if settings.auth_group_sync_dry_run:
            logger.info(
                "sso.group_sync.dry_run",
                extra={
                    "provider": provider,
                    "users": len(provider_users),
                    "groups": len(provider_groups),
                },
            )
            return GroupSyncStats(
                users_upserted=0,
                groups_upserted=0,
                memberships_added=0,
                memberships_removed=0,
            )

        users_by_external = self._upsert_users(provider_users=provider_users)
        return self._upsert_groups_and_memberships(
            provider_groups=provider_groups,
            users_by_external=users_by_external,
        )

    def _upsert_users(self, *, provider_users: list[ProviderUser]) -> dict[str, User]:
        users_by_external: dict[str, User] = {}
        users_upserted = 0
        for provider_user in provider_users:
            stmt: Select[tuple[User]] = select(User).where(
                User.source == "idp",
                User.external_id == provider_user.external_id,
            )
            user = self._session.execute(stmt).scalar_one_or_none()
            if user is None:
                # If email already exists, link to that identity instead of creating a duplicate.
                existing = self._session.execute(
                    select(User).where(User.email_normalized == provider_user.email).limit(1)
                ).scalar_one_or_none()
                if existing is not None:
                    user = existing
                else:
                    user = User(
                        email=provider_user.email,
                        hashed_password=hash_password(mint_opaque_token(32)),
                        display_name=provider_user.display_name,
                        is_active=True,
                        is_verified=False,
                        is_service_account=False,
                    )
                    self._session.add(user)
                    self._session.flush([user])

            user.display_name = provider_user.display_name or user.display_name
            user.source = "idp"
            user.external_id = provider_user.external_id
            user.last_synced_at = utc_now()
            users_by_external[provider_user.external_id] = user
            users_upserted += 1

        logger.info("sso.group_sync.users.upserted", extra={"count": users_upserted})
        return users_by_external

    def _upsert_groups_and_memberships(
        self,
        *,
        provider_groups: list[ProviderGroup],
        users_by_external: dict[str, User],
    ) -> GroupSyncStats:
        groups_upserted = 0
        memberships_added = 0
        memberships_removed = 0

        for provider_group in provider_groups:
            group = self._session.execute(
                select(Group).where(
                    Group.source == GroupSource.IDP,
                    Group.external_id == provider_group.external_id,
                )
            ).scalar_one_or_none()
            if group is None:
                slug_base = _slugify(provider_group.slug_hint or provider_group.display_name)
                slug = slug_base
                while self._session.execute(
                    select(Group.id).where(Group.slug == slug).limit(1)
                ).scalar_one_or_none():
                    slug = f"{slug_base}-{uuid4().hex[:6]}"

                group = Group(
                    display_name=provider_group.display_name,
                    slug=slug,
                    description=provider_group.description,
                    membership_mode=GroupMembershipMode.DYNAMIC,
                    source=GroupSource.IDP,
                    external_id=provider_group.external_id,
                    is_active=True,
                )
                self._session.add(group)
                self._session.flush([group])
            else:
                group.display_name = provider_group.display_name
                group.description = provider_group.description
                group.membership_mode = (
                    GroupMembershipMode.DYNAMIC
                    if provider_group.dynamic
                    else GroupMembershipMode.ASSIGNED
                )
                group.is_active = True

            groups_upserted += 1

            desired_user_ids = {
                users_by_external[external_id].id
                for external_id in provider_group.member_external_ids
                if external_id in users_by_external
            }
            existing_memberships = self._session.execute(
                select(GroupMembership).where(GroupMembership.group_id == group.id)
            ).scalars().all()
            existing_user_ids = {membership.user_id for membership in existing_memberships}

            for user_id in desired_user_ids - existing_user_ids:
                self._session.add(
                    GroupMembership(
                        group_id=group.id,
                        user_id=user_id,
                        membership_source="idp",
                    )
                )
                memberships_added += 1

            for membership in existing_memberships:
                if (
                    membership.user_id not in desired_user_ids
                    and membership.membership_source == "idp"
                ):
                    self._session.delete(membership)
                    memberships_removed += 1

        logger.info(
            "sso.group_sync.groups.reconciled",
            extra={
                "groups_upserted": groups_upserted,
                "memberships_added": memberships_added,
                "memberships_removed": memberships_removed,
            },
        )
        return GroupSyncStats(
            users_upserted=len(users_by_external),
            groups_upserted=groups_upserted,
            memberships_added=memberships_added,
            memberships_removed=memberships_removed,
        )


__all__ = ["EntraGraphAdapter", "GroupSyncService", "GroupSyncStats"]
