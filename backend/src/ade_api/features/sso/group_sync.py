"""IdP group synchronization for dynamic provider-managed memberships."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_api.common.time import utc_now
from ade_api.settings import Settings
from ade_db.models import Group, GroupMembership, GroupMembershipMode, GroupSource, User

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized or "group"


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
    known_users_linked: int
    users_created: int
    groups_upserted: int
    memberships_added: int
    memberships_removed: int
    unknown_members_skipped: int


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

    def fetch_groups_for_user(self, *, user_external_id: str) -> list[ProviderGroup]:
        token = self._access_token()
        records = self._collect_pages(
            token,
            "https://graph.microsoft.com/v1.0/users/"
            f"{user_external_id}/memberOf"
            "?$select=id,displayName,description,mailNickname,groupTypes,membershipRule",
        )
        groups: list[ProviderGroup] = []
        for record in records:
            # memberOf can contain non-group directory objects.
            object_type = str(record.get("@odata.type") or "").strip().lower()
            if object_type and object_type != "#microsoft.graph.group":
                continue
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
            groups.append(
                ProviderGroup(
                    external_id=external_id,
                    display_name=display_name,
                    description=str(record.get("description") or "").strip() or None,
                    slug_hint=str(record.get("mailNickname") or "").strip() or None,
                    dynamic=dynamic,
                    member_external_ids=(user_external_id,),
                )
            )
        return groups


class GroupSyncService:
    """Hydrate provider-managed group memberships for a signed-in user."""

    def __init__(self, *, session: Session) -> None:
        self._session = session

    def sync_user_memberships(
        self,
        *,
        settings: Settings,
        user: User,
        user_external_id: str,
    ) -> GroupSyncStats:
        provider = (settings.auth_group_sync_provider or "").strip().lower()
        if provider != "entra":
            raise RuntimeError(f"Unsupported group sync provider: {provider!r}")

        if not user.external_id or user.external_id == user_external_id:
            user.source = "idp"
            user.external_id = user_external_id
            user.last_synced_at = utc_now()

        adapter = EntraGraphAdapter(settings=settings)
        provider_groups = adapter.fetch_groups_for_user(user_external_id=user_external_id)
        return self._reconcile_user_groups(user=user, provider_groups=provider_groups)

    def _upsert_group(self, *, provider_group: ProviderGroup) -> Group:
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
                membership_mode=(
                    GroupMembershipMode.DYNAMIC
                    if provider_group.dynamic
                    else GroupMembershipMode.ASSIGNED
                ),
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
        return group

    def _reconcile_user_groups(
        self,
        *,
        user: User,
        provider_groups: list[ProviderGroup],
    ) -> GroupSyncStats:
        groups_upserted = 0
        memberships_added = 0
        memberships_removed = 0
        desired_group_ids: set[UUID] = set()

        for provider_group in provider_groups:
            group = self._upsert_group(provider_group=provider_group)
            groups_upserted += 1
            desired_group_ids.add(group.id)

        existing_memberships = self._session.execute(
            select(GroupMembership)
            .join(Group, Group.id == GroupMembership.group_id)
            .where(
                GroupMembership.user_id == user.id,
                GroupMembership.membership_source == "idp",
                Group.source == GroupSource.IDP,
            )
        ).scalars().all()
        existing_group_ids = {membership.group_id for membership in existing_memberships}

        for group_id in desired_group_ids - existing_group_ids:
            self._session.add(
                GroupMembership(
                    group_id=group_id,
                    user_id=user.id,
                    membership_source="idp",
                )
            )
            memberships_added += 1

        for membership in existing_memberships:
            if membership.group_id not in desired_group_ids:
                self._session.delete(membership)
                memberships_removed += 1

        return GroupSyncStats(
            known_users_linked=1,
            users_created=0,
            groups_upserted=groups_upserted,
            memberships_added=memberships_added,
            memberships_removed=memberships_removed,
            unknown_members_skipped=0,
        )


__all__ = ["EntraGraphAdapter", "GroupSyncService", "GroupSyncStats"]
