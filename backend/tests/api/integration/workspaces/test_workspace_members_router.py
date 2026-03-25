from __future__ import annotations

from uuid import uuid4

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_api.features.rbac.service import RbacService
from ade_api.features.workspaces.effective_members import EffectiveWorkspaceMembersResolver
from ade_db.models import (
    AssignmentScopeType,
    PrincipalType,
    RoleAssignment,
    User,
    UserRoleAssignment,
    WorkspaceMembership,
)
from tests.api.integration.helpers_access import (
    add_workspace_membership,
    assign_workspace_role,
    create_group_with_workspace_role,
    create_user,
    role_id_by_slug,
)
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def _auth_headers(async_client: AsyncClient, user) -> dict[str, str]:
    token, _ = await login(async_client, email=user.email, password=user.password)
    return {"X-API-Key": token}


def _create_zero_access_workspace_role(db_session, *, actor: User):
    role = RbacService(session=db_session).create_role(
        name=f"Zero Access {uuid4().hex[:8]}",
        slug=f"zero-access-{uuid4().hex[:8]}",
        description="Workspace-scoped test role without permissions.",
        permissions=[],
        actor=actor,
    )
    return role.id


async def test_workspace_reader_lists_effective_members_and_searches_by_identity(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    owner = db_session.get(User, seed_identity.workspace_owner.id)
    member = db_session.get(User, seed_identity.member.id)
    manager = db_session.get(User, seed_identity.member_with_manage.id)
    indirect = db_session.get(User, seed_identity.orphan.id)
    assert owner is not None
    assert member is not None
    assert manager is not None
    assert indirect is not None

    owner.display_name = "Alpha Owner"
    member.display_name = "Beta Member"
    indirect.display_name = "Delta Group"
    manager.display_name = "Gamma Manager"

    group = create_group_with_workspace_role(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=seed_identity.orphan.id,
        display_name="Indirect Collaborators",
        slug=f"indirect-collaborators-{uuid4().hex[:8]}",
    )
    membership_only = create_user(
        db_session,
        email=f"membership-only-{uuid4().hex[:8]}@example.com",
        password="membership-pass",
        display_name="Membership Only",
    )
    add_workspace_membership(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=membership_only.id,
    )
    inactive_member = create_user(
        db_session,
        email=f"inactive-{uuid4().hex[:8]}@example.com",
        password="inactive-pass",
        display_name="Inactive Member",
        is_active=False,
    )
    add_workspace_membership(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=inactive_member.id,
    )
    assign_workspace_role(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=inactive_member.id,
        role_slug="workspace-member",
    )
    service_account = create_user(
        db_session,
        email=f"service-{uuid4().hex[:8]}@example.com",
        password="service-pass",
        display_name="Service Account",
        is_service_account=True,
    )
    add_workspace_membership(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=service_account.id,
    )
    assign_workspace_role(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=service_account.id,
        role_slug="workspace-member",
    )
    await anyio.to_thread.run_sync(db_session.commit)

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers=await _auth_headers(async_client, seed_identity.member),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    listed_ids = [item["user_id"] for item in payload["items"]]
    assert listed_ids == [
        str(seed_identity.workspace_owner.id),
        str(seed_identity.member.id),
        str(seed_identity.orphan.id),
        str(seed_identity.member_with_manage.id),
    ]
    assert str(membership_only.id) not in listed_ids
    assert str(inactive_member.id) not in listed_ids
    assert str(service_account.id) not in listed_ids

    direct_member = next(
        item for item in payload["items"] if item["user_id"] == str(seed_identity.member.id)
    )
    assert direct_member["access_mode"] == "direct"
    assert direct_member["is_directly_managed"] is True
    assert direct_member["user"] == {
        "id": str(seed_identity.member.id),
        "email": seed_identity.member.email,
        "display_name": "Beta Member",
    }
    assert direct_member["sources"][0]["principal_type"] == "user"
    assert direct_member["sources"][0]["principal_id"] == str(seed_identity.member.id)
    assert direct_member["sources"][0]["principal_email"] == seed_identity.member.email
    assert direct_member["sources"][0]["role_slugs"] == ["workspace-member"]

    indirect_member = next(
        item for item in payload["items"] if item["user_id"] == str(seed_identity.orphan.id)
    )
    assert indirect_member["access_mode"] == "indirect"
    assert indirect_member["is_directly_managed"] is False
    assert indirect_member["user"] == {
        "id": str(seed_identity.orphan.id),
        "email": seed_identity.orphan.email,
        "display_name": "Delta Group",
    }
    assert indirect_member["role_slugs"] == ["workspace-member"]
    assert len(indirect_member["sources"]) == 1
    indirect_source = indirect_member["sources"][0]
    assert indirect_source["principal_type"] == "group"
    assert indirect_source["principal_id"] == str(group.id)
    assert indirect_source["principal_display_name"] == "Indirect Collaborators"
    assert indirect_source["principal_slug"] == group.slug
    assert indirect_source["role_ids"] == indirect_member["role_ids"]
    assert indirect_source["role_slugs"] == ["workspace-member"]

    search_by_name = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        params={"q": "delta"},
        headers=await _auth_headers(async_client, seed_identity.member),
    )
    assert search_by_name.status_code == 200, search_by_name.text
    assert [item["user_id"] for item in search_by_name.json()["items"]] == [
        str(seed_identity.orphan.id)
    ]

    search_by_email = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        params={"q": seed_identity.member_with_manage.email.split("@")[0]},
        headers=await _auth_headers(async_client, seed_identity.member),
    )
    assert search_by_email.status_code == 200, search_by_email.text
    assert [item["user_id"] for item in search_by_email.json()["items"]] == [
        str(seed_identity.member_with_manage.id)
    ]


async def test_member_writes_only_manage_direct_grants_for_indirect_members(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    create_group_with_workspace_role(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=seed_identity.orphan.id,
        display_name="Indirect Collaborators",
        slug=f"indirect-collaborators-{uuid4().hex[:8]}",
    )
    await anyio.to_thread.run_sync(db_session.commit)

    owner_headers = await _auth_headers(async_client, seed_identity.workspace_owner)
    list_before = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers=owner_headers,
    )
    assert list_before.status_code == 200, list_before.text
    before_member = next(
        item
        for item in list_before.json()["items"]
        if item["user_id"] == str(seed_identity.orphan.id)
    )
    assert before_member["access_mode"] == "indirect"
    assert before_member["is_directly_managed"] is False
    assert {source["principal_type"] for source in before_member["sources"]} == {"group"}

    member_role_id = role_id_by_slug(db_session, "workspace-member")
    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers=owner_headers,
        json={
            "user_id": str(seed_identity.orphan.id),
            "role_ids": [str(member_role_id)],
        },
    )
    assert created.status_code == 201, created.text
    created_payload = created.json()
    assert created_payload["access_mode"] == "mixed"
    assert created_payload["is_directly_managed"] is True
    assert {source["principal_type"] for source in created_payload["sources"]} == {
        "group",
        "user",
    }
    assert created_payload["role_slugs"] == ["workspace-member"]

    await anyio.to_thread.run_sync(db_session.expire_all)
    membership = db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == seed_identity.workspace_id,
            WorkspaceMembership.user_id == seed_identity.orphan.id,
        )
    ).scalar_one_or_none()
    assert membership is not None

    deleted = await async_client.delete(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members/{seed_identity.orphan.id}",
        headers=owner_headers,
    )
    assert deleted.status_code == 204, deleted.text

    list_after = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers=owner_headers,
    )
    assert list_after.status_code == 200, list_after.text
    after_member = next(
        item
        for item in list_after.json()["items"]
        if item["user_id"] == str(seed_identity.orphan.id)
    )
    assert after_member["access_mode"] == "indirect"
    assert after_member["is_directly_managed"] is False
    assert {source["principal_type"] for source in after_member["sources"]} == {"group"}

    await anyio.to_thread.run_sync(db_session.expire_all)
    membership = db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == seed_identity.workspace_id,
            WorkspaceMembership.user_id == seed_identity.orphan.id,
        )
    ).scalar_one_or_none()
    assert membership is None

    direct_legacy = db_session.execute(
        select(UserRoleAssignment.id).where(
            UserRoleAssignment.workspace_id == seed_identity.workspace_id,
            UserRoleAssignment.user_id == seed_identity.orphan.id,
            UserRoleAssignment.role_id == member_role_id,
        )
    ).scalar_one_or_none()
    assert direct_legacy is None

    direct_v2 = db_session.execute(
        select(RoleAssignment.id).where(
            RoleAssignment.principal_type == PrincipalType.USER,
            RoleAssignment.principal_id == seed_identity.orphan.id,
            RoleAssignment.role_id == member_role_id,
            RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
            RoleAssignment.scope_id == seed_identity.workspace_id,
        )
    ).scalar_one_or_none()
    assert direct_v2 is None


async def test_member_create_rejects_non_member_roles_before_mutation(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    owner = db_session.get(User, seed_identity.workspace_owner.id)
    assert owner is not None
    zero_access_role_id = _create_zero_access_workspace_role(db_session, actor=owner)
    target = create_user(
        db_session,
        email=f"zero-access-target-{uuid4().hex[:8]}@example.com",
        password="target-pass",
        display_name="Zero Access Target",
    )
    await anyio.to_thread.run_sync(db_session.commit)

    response = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers=await _auth_headers(async_client, seed_identity.workspace_owner),
        json={
            "user_id": str(target.id),
            "role_ids": [str(zero_access_role_id)],
        },
    )

    assert response.status_code == 422, response.text
    payload = response.json()
    assert str(zero_access_role_id) in payload["detail"]

    await anyio.to_thread.run_sync(db_session.expire_all)
    membership = db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == seed_identity.workspace_id,
            WorkspaceMembership.user_id == target.id,
        )
    ).scalar_one_or_none()
    assert membership is None

    direct_legacy = db_session.execute(
        select(UserRoleAssignment.id).where(
            UserRoleAssignment.workspace_id == seed_identity.workspace_id,
            UserRoleAssignment.user_id == target.id,
        )
    ).scalar_one_or_none()
    assert direct_legacy is None

    direct_v2 = db_session.execute(
        select(RoleAssignment.id).where(
            RoleAssignment.principal_type == PrincipalType.USER,
            RoleAssignment.principal_id == target.id,
            RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
            RoleAssignment.scope_id == seed_identity.workspace_id,
        )
    ).scalar_one_or_none()
    assert direct_v2 is None


async def test_member_update_rejects_non_member_roles_before_mutation(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    owner = db_session.get(User, seed_identity.workspace_owner.id)
    assert owner is not None
    zero_access_role_id = _create_zero_access_workspace_role(db_session, actor=owner)
    member_role_id = role_id_by_slug(db_session, "workspace-member")
    await anyio.to_thread.run_sync(db_session.commit)

    response = await async_client.put(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members/{seed_identity.member.id}",
        headers=await _auth_headers(async_client, seed_identity.workspace_owner),
        json={"role_ids": [str(zero_access_role_id)]},
    )

    assert response.status_code == 422, response.text
    payload = response.json()
    assert str(zero_access_role_id) in payload["detail"]

    await anyio.to_thread.run_sync(db_session.expire_all)
    membership = db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == seed_identity.workspace_id,
            WorkspaceMembership.user_id == seed_identity.member.id,
        )
    ).scalar_one_or_none()
    assert membership is not None

    original_direct_assignment = db_session.execute(
        select(UserRoleAssignment.id).where(
            UserRoleAssignment.workspace_id == seed_identity.workspace_id,
            UserRoleAssignment.user_id == seed_identity.member.id,
            UserRoleAssignment.role_id == member_role_id,
        )
    ).scalar_one_or_none()
    assert original_direct_assignment is not None

    rejected_direct_assignment = db_session.execute(
        select(UserRoleAssignment.id).where(
            UserRoleAssignment.workspace_id == seed_identity.workspace_id,
            UserRoleAssignment.user_id == seed_identity.member.id,
            UserRoleAssignment.role_id == zero_access_role_id,
        )
    ).scalar_one_or_none()
    assert rejected_direct_assignment is None


async def test_member_create_rejects_inactive_and_service_account_users(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    member_role_id = role_id_by_slug(db_session, "workspace-member")
    inactive_user = create_user(
        db_session,
        email=f"inactive-target-{uuid4().hex[:8]}@example.com",
        password="inactive-pass",
        display_name="Inactive Target",
        is_active=False,
    )
    service_account = create_user(
        db_session,
        email=f"service-target-{uuid4().hex[:8]}@example.com",
        password="service-pass",
        display_name="Service Target",
        is_service_account=True,
    )
    await anyio.to_thread.run_sync(db_session.commit)

    owner_headers = await _auth_headers(async_client, seed_identity.workspace_owner)
    inactive_response = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers=owner_headers,
        json={
            "user_id": str(inactive_user.id),
            "role_ids": [str(member_role_id)],
        },
    )
    assert inactive_response.status_code == 422, inactive_response.text
    assert inactive_response.json()["detail"] == "User must be active to be a workspace member"

    service_response = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers=owner_headers,
        json={
            "user_id": str(service_account.id),
            "role_ids": [str(member_role_id)],
        },
    )
    assert service_response.status_code == 422, service_response.text
    assert service_response.json()["detail"] == "Service accounts cannot be workspace members"


async def test_effective_members_resolver_does_not_call_per_user_permission_checks(
    seed_identity,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_group_with_workspace_role(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=seed_identity.orphan.id,
        display_name="Resolver Group",
        slug=f"resolver-group-{uuid4().hex[:8]}",
    )
    await anyio.to_thread.run_sync(db_session.commit)

    def _fail(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("resolver should not call per-user workspace permission checks")

    monkeypatch.setattr(RbacService, "get_workspace_permissions_for_user", _fail)

    resolver = EffectiveWorkspaceMembersResolver(session=db_session)
    members = resolver.list_members(workspace_id=seed_identity.workspace_id)

    assert {member.user.id for member in members} == {
        seed_identity.workspace_owner.id,
        seed_identity.member.id,
        seed_identity.member_with_manage.id,
        seed_identity.orphan.id,
    }
