"""Integration tests covering workspace membership routes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_api.features.roles.models import (
    Permission,
    Principal,
    Role,
    RoleAssignment,
    RolePermission,
    ScopeType,
)
from ade_api.features.roles.service import assign_global_role
from ade_api.features.workspaces.models import WorkspaceMembership
from ade_api.settings import get_settings
from ade_api.shared.db.session import get_sessionmaker

pytestmark = pytest.mark.asyncio
SESSION_COOKIE = get_settings().session_cookie_name


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/session",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get(SESSION_COOKIE)
    assert token, "Session cookie missing"
    return token


async def _create_workspace(
    client: AsyncClient,
    admin: dict[str, Any],
    *,
    owner_user_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    token = await _login(client, admin["email"], admin["password"])
    workspace_name = name or f"Workspace {uuid4().hex[:8]}"
    payload: dict[str, Any] = {"name": workspace_name}
    if owner_user_id is not None:
        payload["owner_user_id"] = owner_user_id

    response = await client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_global_permission_allows_workspace_creation(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    session_factory = get_sessionmaker()
    role_slug = f"workspace-creator-{uuid4().hex[:8]}"
    async with session_factory() as session:
        role = Role(
            slug=role_slug,
            name="Workspace Creator",
            scope_type=ScopeType.GLOBAL,
            scope_id=None,
            description="Allows workspace creation",
            built_in=False,
            editable=True,
        )
        session.add(role)
        await session.flush()
        permission = await session.execute(
            select(Permission).where(Permission.key == "Workspaces.Create")
        )
        permission_record = permission.scalar_one()
        session.add(
            RolePermission(role_id=role.id, permission_id=permission_record.id)
        )
        await assign_global_role(
            session=session, user_id=member["id"], role_id=role.id
        )
        await session.commit()

    response = await async_client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"Workspace {uuid4().hex[:8]}"},
    )
    assert response.status_code == 201, response.text


async def test_member_profile_includes_permissions(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity['workspace_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == seed_identity["workspace_id"]
    assert payload["roles"] == ["workspace-member"]
    permissions = set(payload.get("permissions", []))
    assert "Workspace.Documents.ReadWrite" in permissions
    assert "Workspace.Members.ReadWrite" not in permissions


async def test_owner_profile_contains_governor_permissions(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    owner = seed_identity["workspace_owner"]
    token = await _login(async_client, owner["email"], owner["password"])

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity['workspace_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["roles"] == ["workspace-owner"]
    permissions = set(payload["permissions"])
    assert {"Workspace.Roles.ReadWrite", "Workspace.Members.ReadWrite"}.issubset(
        permissions
    )


async def test_admin_profile_shadows_owner(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity['workspace_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["roles"] == ["workspace-owner"]
    assert "Workspace.Settings.ReadWrite" in payload["permissions"]


async def test_members_listing_requires_permission(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity['workspace_id']}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_owner_can_list_members(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    owner = seed_identity["workspace_owner"]
    token = await _login(async_client, owner["email"], owner["password"])

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity['workspace_id']}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    entries = payload["items"]
    assert any(entry["roles"] == ["workspace-owner"] for entry in entries)


async def test_owner_adds_member_with_default_role(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    admin = seed_identity["admin"]
    owner = seed_identity["workspace_owner"]
    invitee = seed_identity["invitee"]
    created = await _create_workspace(async_client, admin, owner_user_id=owner["id"])

    token = await _login(async_client, owner["email"], owner["password"])
    response = await async_client.post(
        f"/api/v1/workspaces/{created['id']}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": invitee["id"]},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["roles"] == ["workspace-member"]
    assert payload["user"]["id"] == invitee["id"]


async def test_manage_scope_required_for_member_add(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    member = seed_identity["member"]
    invitee = seed_identity["invitee"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.post(
        f"/api/v1/workspaces/{seed_identity['workspace_id']}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": invitee["id"]},
    )
    assert response.status_code == 403


async def test_put_roles_replaces_assignments(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    owner = seed_identity["workspace_owner"]
    invitee = seed_identity["invitee"]
    workspace_id = seed_identity["workspace_id"]

    token = await _login(async_client, owner["email"], owner["password"])
    add_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": invitee["id"]},
    )
    assert add_response.status_code == 201, add_response.text
    membership_id = add_response.json()["id"]

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            select(Role).where(Role.slug == "workspace-owner")
        )
        owner_role = result.scalar_one()

    update_response = await async_client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{membership_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={"role_ids": [owner_role.id]},
    )
    assert update_response.status_code == 200, update_response.text
    payload = update_response.json()
    assert payload["roles"] == ["workspace-owner"]

    async with session_factory() as session:
        membership = await session.get(WorkspaceMembership, membership_id)
        assert membership is not None
        role_links = await session.execute(
            select(RoleAssignment.role_id)
            .join(Principal, Principal.id == RoleAssignment.principal_id)
            .where(
                Principal.user_id == membership.user_id,
                RoleAssignment.scope_type == ScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
            )
        )
        linked_roles = list(role_links.scalars().all())
        assert linked_roles == [owner_role.id]


async def test_put_roles_blocks_last_governor_demotion(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    owner = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]

    token = await _login(async_client, owner["email"], owner["password"])
    memberships_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    owner_entry = next(
        entry
        for entry in memberships_response.json()["items"]
        if entry["roles"] == ["workspace-owner"]
    )

    update_response = await async_client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_entry['id']}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={"role_ids": []},
    )
    assert update_response.status_code == 409


async def test_roles_listing_requires_read_scope(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    owner = seed_identity["workspace_owner"]
    token = await _login(async_client, owner["email"], owner["password"])

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity['workspace_id']}/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    slugs = {entry["slug"] for entry in payload["items"]}
    assert {"workspace-owner", "workspace-member"}.issubset(slugs)


async def test_create_workspace_role(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    owner = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(async_client, owner["email"], owner["password"])

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Contributors",
            "slug": "Contributors",
            "permissions": ["Workspace.Documents.Read"],
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["slug"] == "contributors"
    assert payload["scope_type"] == ScopeType.WORKSPACE.value
    assert payload["scope_id"] == workspace_id
    assert payload["permissions"] == ["Workspace.Documents.Read"]


async def test_create_workspace_role_conflicting_slug(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    owner = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(async_client, owner["email"], owner["password"])

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Duplicate",
            "slug": "workspace-owner",
            "permissions": ["Workspace.Documents.Read"],
        },
    )

    assert response.status_code == 409


async def test_update_workspace_role_blocks_governor_loss(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    owner = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(async_client, owner["email"], owner["password"])

    create_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Workspace Governor",
            "permissions": [
                "Workspace.Roles.ReadWrite",
                "Workspace.Members.ReadWrite",
                "Workspace.Settings.ReadWrite",
            ],
        },
    )
    assert create_response.status_code == 201, create_response.text
    role_payload = create_response.json()
    role_id = role_payload["id"]

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        membership = (
            await session.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.user_id == owner["id"],
                    WorkspaceMembership.workspace_id == workspace_id,
                )
            )
        ).scalar_one()
        membership_id = membership.user_id

    update_membership = await async_client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{membership_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={"role_ids": [role_id]},
    )
    assert update_membership.status_code == 200, update_membership.text

    downgrade_response = await async_client.put(
        f"/api/v1/workspaces/{workspace_id}/roles/{role_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Workspace Governor",
            "permissions": ["Workspace.Roles.ReadWrite"],
        },
    )
    assert downgrade_response.status_code == 409


async def test_delete_workspace_role_blocks_assignments(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    owner = seed_identity["workspace_owner"]
    member = seed_identity["member"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(async_client, owner["email"], owner["password"])

    create_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Temporary",
            "permissions": ["Workspace.Documents.Read"],
        },
    )
    assert create_response.status_code == 201, create_response.text
    role_id = create_response.json()["id"]

    list_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200, list_response.text
    member_entry = next(
        entry
        for entry in list_response.json()["items"]
        if entry["user"]["id"] == member["id"]
    )

    assign_response = await async_client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{member_entry['id']}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={"role_ids": [role_id]},
    )
    assert assign_response.status_code == 200, assign_response.text

    delete_response = await async_client.delete(
        f"/api/v1/workspaces/{workspace_id}/roles/{role_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 409


async def test_delete_workspace_role_succeeds_when_unassigned(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    owner = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(async_client, owner["email"], owner["password"])

    create_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Disposable",
            "permissions": ["Workspace.Documents.Read"],
        },
    )
    assert create_response.status_code == 201, create_response.text
    role_id = create_response.json()["id"]

    delete_response = await async_client.delete(
        f"/api/v1/workspaces/{workspace_id}/roles/{role_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204, delete_response.text


async def test_update_system_role_rejected(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    owner = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(async_client, owner["email"], owner["password"])

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        system_role = (
            await session.execute(
                select(Role).where(Role.slug == "workspace-owner")
            )
        ).scalar_one()

    response = await async_client.put(
        f"/api/v1/workspaces/{workspace_id}/roles/{system_role.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Workspace Owner",
            "permissions": ["Workspace.Documents.Read"],
        },
    )

    assert response.status_code == 400
