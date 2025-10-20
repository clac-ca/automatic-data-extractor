from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from backend.app.tests.utils import login



@pytest.mark.asyncio
async def test_permission_catalog_workspace(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    owner = seed_identity["workspace_owner"]
    token, _ = await login(async_client, email=owner["email"], password=owner["password"])

    response = await async_client.get(
        "/api/v1/permissions",
        params={
            "scope": "workspace",
            "workspace_id": seed_identity["workspace_id"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(entry["key"] == "Workspace.Read" for entry in payload)


@pytest.mark.asyncio
async def test_permission_catalog_workspace_requires_access(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    member = seed_identity["member"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.get(
        "/api/v1/permissions",
        params={
            "scope": "workspace",
            "workspace_id": seed_identity["workspace_id"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_permission_catalog_global(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.get(
        "/api/v1/permissions",
        params={"scope": "global"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(entry["key"] == "Roles.Read.All" for entry in payload)


@pytest.mark.asyncio
async def test_list_global_roles_requires_permission(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    member = seed_identity["member"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.get(
        "/api/v1/roles",
        params={"scope": "global"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_global_roles_returns_catalog(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.get(
        "/api/v1/roles",
        params={"scope": "global"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    slugs = {entry["slug"] for entry in payload}
    assert "global-administrator" in slugs


@pytest.mark.asyncio
async def test_create_global_role_requires_permission(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    member = seed_identity["member"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.post(
        "/api/v1/roles",
        params={"scope": "global"},
        json={
            "name": "Limited Auditor",
            "permissions": ["System.Settings.Read"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_update_delete_global_role(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    create_response = await async_client.post(
        "/api/v1/roles",
        params={"scope": "global"},
        json={
            "name": "Data Steward",
            "permissions": ["Users.Read.All"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["slug"] == "data-steward"
    role_id = created["role_id"]

    update_response = await async_client.patch(
        f"/api/v1/roles/{role_id}",
        json={
            "name": "Data Steward",
            "description": "Manages user directory",
            "permissions": ["Users.Read.All", "Users.Invite"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert sorted(updated["permissions"]) == ["Users.Invite", "Users.Read.All"]
    assert updated["description"] == "Manages user directory"

    delete_response = await async_client.delete(
        f"/api/v1/roles/{role_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204, delete_response.text

    missing_response = await async_client.get(
        f"/api/v1/roles/{role_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_list_global_role_assignments_requires_permission(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    member = seed_identity["member"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.get(
        "/api/v1/role-assignments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_global_role_assignment_flow(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    admin = seed_identity["admin"]
    workspace_owner = seed_identity["workspace_owner"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    roles_response = await async_client.get(
        "/api/v1/roles",
        params={"scope": "global"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert roles_response.status_code == 200, roles_response.text
    roles = roles_response.json()
    admin_role = next(
        (entry for entry in roles if entry["slug"] == "global-administrator"),
        None,
    )
    assert admin_role is not None
    admin_role_id = admin_role["role_id"]

    create_response = await async_client.post(
        "/api/v1/role-assignments",
        json={"user_id": workspace_owner["id"], "role_id": admin_role_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assignment_id = created["assignment_id"]
    assert created["role_id"] == admin_role_id
    assert created["user_id"] == workspace_owner["id"]

    duplicate_response = await async_client.post(
        "/api/v1/role-assignments",
        json={"user_id": workspace_owner["id"], "role_id": admin_role_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert duplicate_response.status_code == 200, duplicate_response.text
    duplicate = duplicate_response.json()
    assert duplicate["assignment_id"] == assignment_id

    list_response = await async_client.get(
        "/api/v1/role-assignments",
        params={"role_id": admin_role_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200, list_response.text
    assignments = list_response.json()
    assert any(item["user_id"] == workspace_owner["id"] for item in assignments)

    delete_response = await async_client.delete(
        f"/api/v1/role-assignments/{assignment_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204, delete_response.text

    post_delete = await async_client.get(
        "/api/v1/role-assignments",
        params={"role_id": admin_role_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert post_delete.status_code == 200
    remaining = post_delete.json()
    assert all(item["user_id"] != workspace_owner["id"] for item in remaining)


@pytest.mark.asyncio
async def test_list_workspace_role_assignments_requires_permission(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    member = seed_identity["member"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity['workspace_id']}/role-assignments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_workspace_role_assignment_flow(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    owner = seed_identity["workspace_owner"]
    member_manage = seed_identity["member_with_manage"]
    workspace_id = seed_identity["workspace_id"]
    token, _ = await login(async_client, email=owner["email"], password=owner["password"])

    roles_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert roles_response.status_code == 200, roles_response.text
    roles = roles_response.json()
    owner_role = next(
        (entry for entry in roles if entry["slug"] == "workspace-owner"),
        None,
    )
    assert owner_role is not None
    owner_role_id = owner_role["role_id"]

    create_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/role-assignments",
        json={"user_id": member_manage["id"], "role_id": owner_role_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assignment_id = created["assignment_id"]
    assert created["role_id"] == owner_role_id
    assert created["user_id"] == member_manage["id"]

    duplicate_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/role-assignments",
        json={"user_id": member_manage["id"], "role_id": owner_role_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert duplicate_response.status_code == 200, duplicate_response.text
    assert duplicate_response.json()["assignment_id"] == assignment_id

    list_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/role-assignments",
        params={"role_id": owner_role_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200, list_response.text
    assignments = list_response.json()
    assert any(item["user_id"] == member_manage["id"] for item in assignments)

    delete_response = await async_client.delete(
        f"/api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204, delete_response.text

    after_delete = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/role-assignments",
        params={"role_id": owner_role_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert after_delete.status_code == 200
    remaining = after_delete.json()
    assert all(item["user_id"] != member_manage["id"] for item in remaining)


@pytest.mark.asyncio
async def test_read_effective_permissions(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    owner = seed_identity["workspace_owner"]
    token, _ = await login(async_client, email=owner["email"], password=owner["password"])

    response = await async_client.get(
        "/api/v1/me/permissions",
        params={"workspace_id": seed_identity["workspace_id"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_id"] == seed_identity["workspace_id"]
    assert "Workspace.Read" in payload["workspace_permissions"]
    assert payload["global_permissions"] == []


@pytest.mark.asyncio
async def test_check_permissions_requires_workspace_id(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    owner = seed_identity["workspace_owner"]
    token, _ = await login(async_client, email=owner["email"], password=owner["password"])

    response = await async_client.post(
        "/api/v1/me/permissions/check",
        json={"permissions": ["Workspace.Members.Read"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_check_permissions_returns_map(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.post(
        "/api/v1/me/permissions/check",
        json={
            "permissions": [
                "Workspaces.Read.All",
                "Workspace.Members.Read",
            ],
            "workspace_id": seed_identity["workspace_id"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]["Workspaces.Read.All"] is True
    assert payload["results"]["Workspace.Members.Read"] is True
