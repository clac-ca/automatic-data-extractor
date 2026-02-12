from __future__ import annotations

import pytest
from sqlalchemy import select

from ade_api.core.security.hashing import hash_password
from ade_api.features.sso.group_sync import GroupSyncService, ProviderGroup
from ade_db.models import Group, GroupMembership, GroupMembershipMode, GroupSource, User


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


def test_sync_user_memberships_upserts_groups_and_memberships(
    session,
    settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _new_user(email="user_a@example.com")
    session.add(user)
    session.flush()

    class _FakeAdapter:
        def __init__(self, *, settings):
            del settings

        def fetch_groups_for_user(self, *, user_external_id: str) -> list[ProviderGroup]:
            assert user_external_id == "entra-a"
            return [
                ProviderGroup(
                    external_id="group-a",
                    display_name="Group A",
                    description="Synced from Entra",
                    slug_hint="group-a",
                    dynamic=True,
                    member_external_ids=("entra-a",),
                ),
                ProviderGroup(
                    external_id="group-b",
                    display_name="Group B",
                    description=None,
                    slug_hint="group-b",
                    dynamic=False,
                    member_external_ids=("entra-a",),
                )
            ]

    monkeypatch.setattr("ade_api.features.sso.group_sync.EntraGraphAdapter", _FakeAdapter)

    stats = GroupSyncService(session=session).sync_user_memberships(
        settings=settings,
        user=user,
        user_external_id="entra-a",
    )
    session.flush()

    assert stats.known_users_linked == 1
    assert stats.users_created == 0
    assert stats.groups_upserted == 2
    assert stats.memberships_added == 2
    assert stats.memberships_removed == 0
    assert stats.unknown_members_skipped == 0

    session.refresh(user)
    assert user.source == "idp"
    assert user.external_id == "entra-a"

    groups = list(session.execute(select(Group).order_by(Group.display_name.asc())).scalars())
    assert [group.display_name for group in groups] == ["Group A", "Group B"]
    assert groups[0].membership_mode == GroupMembershipMode.DYNAMIC
    assert groups[1].membership_mode == GroupMembershipMode.ASSIGNED
    assert all(group.source == GroupSource.IDP for group in groups)

    memberships = list(
        session.execute(
            select(GroupMembership).where(GroupMembership.user_id == user.id)
        ).scalars()
    )
    assert len(memberships) == 2
    assert all(membership.membership_source == "idp" for membership in memberships)


def test_sync_user_memberships_removes_stale_group_memberships(
    session,
    settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _new_user(email="user_a@example.com", source="idp", external_id="entra-a")
    stale_group = Group(
        display_name="Stale Group",
        slug="stale-group",
        description=None,
        membership_mode=GroupMembershipMode.DYNAMIC,
        source=GroupSource.IDP,
        external_id="stale-group",
        is_active=True,
    )
    kept_group = Group(
        display_name="Kept Group",
        slug="kept-group",
        description=None,
        membership_mode=GroupMembershipMode.DYNAMIC,
        source=GroupSource.IDP,
        external_id="kept-group",
        is_active=True,
    )
    session.add_all([user, stale_group, kept_group])
    session.flush()
    session.add_all(
        [
            GroupMembership(group_id=stale_group.id, user_id=user.id, membership_source="idp"),
            GroupMembership(group_id=kept_group.id, user_id=user.id, membership_source="idp"),
        ]
    )
    session.flush()

    class _FakeAdapter:
        def __init__(self, *, settings):
            del settings

        def fetch_groups_for_user(self, *, user_external_id: str) -> list[ProviderGroup]:
            assert user_external_id == "entra-a"
            return [
                ProviderGroup(
                    external_id="kept-group",
                    display_name="Kept Group",
                    description=None,
                    slug_hint="kept-group",
                    dynamic=True,
                    member_external_ids=("entra-a",),
                )
            ]

    monkeypatch.setattr("ade_api.features.sso.group_sync.EntraGraphAdapter", _FakeAdapter)

    stats = GroupSyncService(session=session).sync_user_memberships(
        settings=settings,
        user=user,
        user_external_id="entra-a",
    )
    session.flush()

    assert stats.known_users_linked == 1
    assert stats.users_created == 0
    assert stats.unknown_members_skipped == 0
    assert stats.memberships_added == 0
    assert stats.memberships_removed == 1

    membership_groups = {
        membership.group_id
        for membership in session.execute(
            select(GroupMembership).where(GroupMembership.user_id == user.id)
        ).scalars()
    }
    assert membership_groups == {kept_group.id}


def test_sync_user_memberships_rejects_unsupported_provider(session, settings) -> None:
    settings.auth_group_sync_provider = "unsupported"  # type: ignore[assignment]
    user = _new_user(email="user_a@example.com")
    session.add(user)
    session.flush()

    with pytest.raises(RuntimeError, match="Unsupported group sync provider"):
        GroupSyncService(session=session).sync_user_memberships(
            settings=settings,
            user=user,
            user_external_id="entra-a",
        )
