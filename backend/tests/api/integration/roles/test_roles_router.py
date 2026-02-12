from __future__ import annotations

import json
from typing import Any

import pytest
from httpx import AsyncClient

from tests.api.utils import login

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
        "/api/v1/permissions",
        params={
            "filters": json.dumps(
                [{"id": "scopeType", "operator": "eq", "value": "workspace"}]
            )
        },
        headers={"X-API-Key": token},
    )

    assert response.status_code == 403


async def test_permission_catalog_global_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        "/api/v1/permissions",
        params={
            "filters": json.dumps(
                [{"id": "scopeType", "operator": "eq", "value": "global"}]
            )
        },
        headers={"X-API-Key": token},
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
        "/api/v1/roles",
        json={
            "name": "Data Steward",
            "permissions": ["users.read_all"],
        },
        headers={"X-API-Key": token},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    role_id = created["id"]
    assert created["slug"] == "data-steward"
    assert created["permissions"] == ["users.read_all"]

    read_response = await async_client.get(
        f"/api/v1/roles/{role_id}",
        headers={"X-API-Key": token},
    )
    assert read_response.status_code == 200, read_response.text
    role_etag = read_response.headers.get("ETag")
    assert role_etag is not None

    update_response = await async_client.patch(
        f"/api/v1/roles/{role_id}",
        json={
            "name": "Data Steward",
            "description": "Manages user directory",
            "permissions": ["users.read_all", "roles.read_all"],
        },
        headers={
            "X-API-Key": token,
            "If-Match": role_etag,
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert sorted(updated["permissions"]) == ["roles.read_all", "users.read_all"]
    assert updated["description"] == "Manages user directory"
    updated_etag = update_response.headers.get("ETag")
    assert updated_etag is not None

    delete_response = await async_client.delete(
        f"/api/v1/roles/{role_id}",
        headers={
            "X-API-Key": token,
            "If-Match": updated_etag,
        },
    )
    assert delete_response.status_code == 204

    missing_response = await async_client.get(
        f"/api/v1/roles/{role_id}",
        headers={"X-API-Key": token},
    )
    assert missing_response.status_code == 404


async def test_workspace_role_assignment_listing_requires_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 403


async def test_workspace_role_assignment_listing_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assignments = _items(payload)
    assert any(
        str(item["principal_id"]) == str(seed_identity.workspace_owner.id)
        and item["principal_type"] == "user"
        for item in assignments
    )


async def test_assign_workspace_principal_roles(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    workspace_id = seed_identity.workspace_id
    user_id = seed_identity.orphan.id
    user_id_str = str(user_id)

    # Reject missing role_id payload.
    create_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roleAssignments",
        json={
            "principal_type": "user",
            "principal_id": user_id_str,
        },
        headers={"X-API-Key": token},
    )
    assert create_response.status_code == 422

    # Load workspace-member role id
    roles_response = await async_client.get(
        "/api/v1/roles",
        params={
            "filters": json.dumps(
                [{"id": "scopeType", "operator": "eq", "value": "workspace"}]
            )
        },
        headers={"X-API-Key": token},
    )
    assert roles_response.status_code == 200
    workspace_roles = {role["slug"]: role["id"] for role in _items(roles_response.json())}
    member_role_id = workspace_roles["workspace-member"]

    create_assignment = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roleAssignments",
        json={
            "principal_type": "user",
            "principal_id": user_id_str,
            "role_id": member_role_id,
        },
        headers={"X-API-Key": token},
    )
    assert create_assignment.status_code == 201, create_assignment.text
    created = create_assignment.json()
    assert created["principal_type"] == "user"
    assert str(created["principal_id"]) == user_id_str
    assert created["role_id"] == member_role_id
    assignment_id = created["id"]

    # Remove assignment
    delete_response = await async_client.delete(
        f"/api/v1/roleAssignments/{assignment_id}",
        headers={"X-API-Key": token},
    )
    assert delete_response.status_code == 204


async def test_group_workspace_assignment_grants_workspace_access(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    orphan = seed_identity.orphan

    roles_response = await async_client.get(
        "/api/v1/roles",
        params={
            "filters": json.dumps(
                [{"id": "scopeType", "operator": "eq", "value": "workspace"}]
            )
        },
        headers={"X-API-Key": admin_token},
    )
    assert roles_response.status_code == 200
    workspace_roles = {role["slug"]: role["id"] for role in _items(roles_response.json())}
    member_role_id = workspace_roles["workspace-member"]

    create_group_response = await async_client.post(
        "/api/v1/groups",
        json={
            "display_name": "Workspace Access Group",
            "slug": "workspace-access-group",
            "membership_mode": "assigned",
            "source": "internal",
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    add_member_response = await async_client.post(
        f"/api/v1/groups/{group_id}/members/$ref",
        json={"memberId": str(orphan.id)},
        headers={"X-API-Key": admin_token},
    )
    assert add_member_response.status_code == 200, add_member_response.text

    create_assignment = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        json={
            "principal_type": "group",
            "principal_id": group_id,
            "role_id": member_role_id,
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_assignment.status_code == 201, create_assignment.text

    orphan_token, _ = await login(async_client, email=orphan.email, password=orphan.password)

    list_workspaces = await async_client.get(
        "/api/v1/workspaces",
        headers={"X-API-Key": orphan_token},
    )
    assert list_workspaces.status_code == 200, list_workspaces.text
    listed_ids = {item["id"] for item in _items(list_workspaces.json())}
    assert str(seed_identity.workspace_id) in listed_ids

    read_workspace = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}",
        headers={"X-API-Key": orphan_token},
    )
    assert read_workspace.status_code == 200, read_workspace.text
    payload = read_workspace.json()
    assert "workspace-member" in payload["roles"]
