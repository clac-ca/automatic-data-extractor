from __future__ import annotations

import pytest
from sqlalchemy import select

from ade_api.core.security.hashing import hash_password
from ade_api.features.sso.group_sync import (
    GroupSyncService,
    ProviderGroup,
    ProviderUser,
)
from ade_api.features.sso.service import SsoService
from ade_db.models import Group, GroupMembership, SsoIdentity, SsoProviderStatus, User


def _create_active_provider(*, session, settings, domains: list[str]) -> str:
    provider = SsoService(session=session, settings=settings).create_provider(
        provider_id="entra",
        label="Microsoft Entra ID",
        issuer="https://login.microsoftonline.com/test-tenant/v2.0",
        client_id="entra-client-id",
        client_secret="entra-client-secret",
        status_value=SsoProviderStatus.ACTIVE,
        domains=domains,
    )
    session.flush()
    return provider.id


def _new_user(*, email: str, source: str = "internal", external_id: str | None = None) -> User:
    return User(
        email=email,
        hashed_password=hash_password("not-used-password"),
        display_name=email.split("@", 1)[0],
        is_active=True,
        is_verified=True,
        is_service_account=False,
        source=source,
        external_id=external_id,
    )


def test_run_once_links_known_users_and_skips_unknown_members(
    session,
    settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.auth_group_sync_dry_run = False
    _create_active_provider(session=session, settings=settings, domains=["example.com"])

    user_a = _new_user(email="user_a@example.com", source="idp", external_id="entra-a")
    user_b = _new_user(email="user_b@example.com")
    session.add_all([user_a, user_b])
    session.flush()

    class _FakeAdapter:
        def __init__(self, *, settings):
            del settings

        def fetch_users(self) -> list[ProviderUser]:
            return [
                ProviderUser(
                    external_id="entra-a",
                    email="user_a@example.com",
                    display_name="User A",
                ),
                ProviderUser(
                    external_id="entra-b",
                    email="user_b@example.com",
                    display_name="User B",
                ),
                ProviderUser(
                    external_id="entra-c",
                    email="user_c@example.com",
                    display_name="User C",
                ),
            ]

        def fetch_groups(self) -> list[ProviderGroup]:
            return [
                ProviderGroup(
                    external_id="group-a",
                    display_name="Group A",
                    description="Synced from Entra",
                    slug_hint="group-a",
                    dynamic=True,
                    member_external_ids=("entra-a", "entra-b", "entra-c"),
                )
            ]

    monkeypatch.setattr("ade_api.features.sso.group_sync.EntraGraphAdapter", _FakeAdapter)

    stats = GroupSyncService(session=session).run_once(settings=settings)
    session.flush()

    assert stats.known_users_linked == 2
    assert stats.users_created == 0
    assert stats.groups_upserted == 1
    assert stats.memberships_added == 2
    assert stats.unknown_members_skipped == 1

    missing_user = session.execute(
        select(User).where(User.email_normalized == "user_c@example.com")
    ).scalar_one_or_none()
    assert missing_user is None

    session.refresh(user_b)
    assert user_b.source == "idp"
    assert user_b.external_id == "entra-b"

    group = session.execute(select(Group).where(Group.external_id == "group-a")).scalar_one()
    member_ids = {
        member.user_id
        for member in session.execute(
            select(GroupMembership).where(GroupMembership.group_id == group.id)
        ).scalars()
    }
    assert member_ids == {user_a.id, user_b.id}


def test_run_once_does_not_link_email_outside_allowed_domains(
    session,
    settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.auth_group_sync_dry_run = False
    _create_active_provider(session=session, settings=settings, domains=["allowed.example.com"])

    blocked_user = _new_user(email="blocked@outside.example.com")
    session.add(blocked_user)
    session.flush()

    class _FakeAdapter:
        def __init__(self, *, settings):
            del settings

        def fetch_users(self) -> list[ProviderUser]:
            return [
                ProviderUser(
                    external_id="entra-blocked",
                    email="blocked@outside.example.com",
                    display_name="Blocked User",
                )
            ]

        def fetch_groups(self) -> list[ProviderGroup]:
            return [
                ProviderGroup(
                    external_id="group-blocked",
                    display_name="Blocked Group",
                    description=None,
                    slug_hint="blocked-group",
                    dynamic=True,
                    member_external_ids=("entra-blocked",),
                )
            ]

    monkeypatch.setattr("ade_api.features.sso.group_sync.EntraGraphAdapter", _FakeAdapter)

    stats = GroupSyncService(session=session).run_once(settings=settings)
    session.flush()

    assert stats.known_users_linked == 0
    assert stats.users_created == 0
    assert stats.memberships_added == 0
    assert stats.unknown_members_skipped == 1

    session.refresh(blocked_user)
    assert blocked_user.source == "internal"
    assert blocked_user.external_id is None


def test_run_once_links_user_via_sso_subject_even_when_email_mismatch(
    session,
    settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.auth_group_sync_dry_run = False
    provider_id = _create_active_provider(
        session=session,
        settings=settings,
        domains=["allowed.example.com"],
    )

    linked_user = _new_user(email="legacy@outside.example.com")
    session.add(linked_user)
    session.flush()
    session.add(
        SsoIdentity(
            provider_id=provider_id,
            subject="tenant-id:entra-linked",
            user_id=linked_user.id,
            email=linked_user.email_normalized,
            email_verified=True,
        )
    )
    session.flush()

    class _FakeAdapter:
        def __init__(self, *, settings):
            del settings

        def fetch_users(self) -> list[ProviderUser]:
            return [
                ProviderUser(
                    external_id="entra-linked",
                    email="new-email@outside.example.com",
                    display_name="Renamed User",
                )
            ]

        def fetch_groups(self) -> list[ProviderGroup]:
            return [
                ProviderGroup(
                    external_id="group-linked",
                    display_name="Linked Group",
                    description=None,
                    slug_hint="linked-group",
                    dynamic=True,
                    member_external_ids=("entra-linked",),
                )
            ]

    monkeypatch.setattr("ade_api.features.sso.group_sync.EntraGraphAdapter", _FakeAdapter)

    stats = GroupSyncService(session=session).run_once(settings=settings)
    session.flush()

    assert stats.known_users_linked == 1
    assert stats.users_created == 0
    assert stats.unknown_members_skipped == 0

    session.refresh(linked_user)
    assert linked_user.source == "idp"
    assert linked_user.external_id == "entra-linked"
    assert linked_user.display_name == "Renamed User"
