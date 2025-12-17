from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from ade_api.models import User
from tests.utils import login

pytestmark = pytest.mark.asyncio


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    return payload["items"]


async def test_permission_catalog_requires_global_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        "/api/v1/rbac/permissions",
        params={"scope": "workspace"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_permission_catalog_global_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        "/api/v1/rbac/permissions",
        params={"scope": "global"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    records = _items(payload)
    keys = {entry["key"] for entry in records}
    assert "roles.read_all" in keys
    assert "users.read_all" in keys


async def test_roles_crud_and_delete(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    create_response = await async_client.post(
        "/api/v1/rbac/roles",
        params={"scope": "global"},
        json={
            "name": "Data Steward",
            "permissions": ["users.read_all"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    role_id = created["id"]
    assert created["slug"] == "data-steward"
    assert created["permissions"] == ["users.read_all"]

    update_response = await async_client.patch(
        f"/api/v1/rbac/roles/{role_id}",
        json={
            "name": "Data Steward",
            "description": "Manages user directory",
            "permissions": ["users.read_all", "roles.read_all"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert sorted(updated["permissions"]) == ["roles.read_all", "users.read_all"]
    assert updated["description"] == "Manages user directory"

    delete_response = await async_client.delete(
        f"/api/v1/rbac/roles/{role_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204

    missing_response = await async_client.get(
        f"/api/v1/rbac/roles/{role_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing_response.status_code == 404


async def test_workspace_member_listing_requires_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_workspace_member_listing_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    members = _items(payload)
    assert any(str(m["user_id"]) == str(seed_identity.workspace_owner.id) for m in members)


async def test_workspace_member_listing_excludes_inactive_by_default(
    async_client: AsyncClient,
    seed_identity,
    session,
) -> None:
    admin = seed_identity.admin
    member = seed_identity.member
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    user = await session.get(User, member.id)
    assert user is not None
    user.is_active = False
    await session.flush()

    base_url = f"/api/v1/workspaces/{seed_identity.workspace_id}/members"

    default_response = await async_client.get(
        base_url,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert default_response.status_code == 200
    default_members = {str(item["user_id"]) for item in _items(default_response.json())}
    assert str(member.id) not in default_members

    inclusive = await async_client.get(
        base_url,
        headers={"Authorization": f"Bearer {token}"},
        params={"include_inactive": True},
    )
    assert inclusive.status_code == 200, inclusive.text
    inclusive_members = {str(item["user_id"]) for item in _items(inclusive.json())}
    assert str(member.id) in inclusive_members


async def test_assign_workspace_member_roles(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    workspace_id = seed_identity.workspace_id
    user_id = seed_identity.orphan.id
    user_id_str = str(user_id)

    # Assign workspace-member to a user without existing membership
    create_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={
            "user_id": user_id_str,
            "role_ids": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 422  # must include role_ids

    # Load workspace-member role id
    roles_response = await async_client.get(
        "/api/v1/rbac/roles",
        params={"scope": "workspace"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert roles_response.status_code == 200
    workspace_roles = {role["slug"]: role["id"] for role in _items(roles_response.json())}
    member_role_id = workspace_roles["workspace-member"]

    add_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"user_id": user_id_str, "role_ids": [member_role_id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add_response.status_code == 201, add_response.text
    added = add_response.json()
    assert str(added["user_id"]) == user_id_str
    assert member_role_id in added["role_ids"]

    # Remove membership
    delete_response = await async_client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204
