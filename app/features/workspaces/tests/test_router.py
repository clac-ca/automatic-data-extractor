"""Integration tests covering workspace membership routes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.features.roles.models import Role
from app.features.workspaces.models import WorkspaceMembership, WorkspaceMembershipRole

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/auth/session",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get("ade_session")
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
        "/api/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_member_profile_includes_permissions(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        f"/api/workspaces/{seed_identity['workspace_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_id"] == seed_identity["workspace_id"]
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
        f"/api/workspaces/{seed_identity['workspace_id']}",
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
        f"/api/workspaces/{seed_identity['workspace_id']}",
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
        f"/api/workspaces/{seed_identity['workspace_id']}/members",
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
        f"/api/workspaces/{seed_identity['workspace_id']}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert any(entry["roles"] == ["workspace-owner"] for entry in payload)


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
        f"/api/workspaces/{created['workspace_id']}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": invitee["id"]},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["roles"] == ["workspace-member"]
    assert payload["user"]["user_id"] == invitee["id"]


async def test_manage_scope_required_for_member_add(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    member = seed_identity["member"]
    invitee = seed_identity["invitee"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.post(
        f"/api/workspaces/{seed_identity['workspace_id']}/members",
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
        f"/api/workspaces/{workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": invitee["id"]},
    )
    assert add_response.status_code == 201, add_response.text
    membership_id = add_response.json()["workspace_membership_id"]

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            select(Role).where(Role.slug == "workspace-owner")
        )
        owner_role = result.scalar_one()

    update_response = await async_client.put(
        f"/api/workspaces/{workspace_id}/members/{membership_id}/roles",
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
            select(WorkspaceMembershipRole).where(
                WorkspaceMembershipRole.workspace_membership_id == membership_id
            )
        )
        linked_roles = [link.role_id for link in role_links.scalars()]
        assert linked_roles == [owner_role.id]


async def test_put_roles_blocks_last_governor_demotion(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    owner = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]

    token = await _login(async_client, owner["email"], owner["password"])
    memberships_response = await async_client.get(
        f"/api/workspaces/{workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    owner_entry = next(
        entry
        for entry in memberships_response.json()
        if entry["roles"] == ["workspace-owner"]
    )

    update_response = await async_client.put(
        f"/api/workspaces/{workspace_id}/members/{owner_entry['workspace_membership_id']}/roles",
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
        f"/api/workspaces/{seed_identity['workspace_id']}/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    slugs = {entry["slug"] for entry in payload}
    assert {"workspace-owner", "workspace-member"}.issubset(slugs)
