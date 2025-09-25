"""Workspace endpoint coverage."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from backend.api.db.session import get_sessionmaker
from backend.api.modules.workspaces.models import WorkspaceMembership, WorkspaceRole


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_workspace_context_returns_membership(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Members should resolve context when calling the workspace-specific route."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        f"/workspaces/{seed_identity['workspace_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    workspace_payload = payload["workspace"]
    assert workspace_payload["workspace_id"] == seed_identity["workspace_id"]
    permissions = set(workspace_payload.get("permissions", []))
    assert "workspace:documents:write" in permissions
    assert "workspace:members:manage" not in permissions


@pytest.mark.asyncio
async def test_workspace_owner_receives_membership_permissions(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Workspace owners should inherit management permissions for members and settings."""

    workspace_owner = seed_identity["workspace_owner"]
    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    workspace_id = seed_identity["workspace_id"]
    response = await async_client.get(
        f"/workspaces/{workspace_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "workspace" in payload
    permissions = set(payload["workspace"].get("permissions", []))
    assert "workspace:members:read" in permissions
    assert "workspace:members:manage" in permissions
    assert "workspace:settings:manage" in permissions


@pytest.mark.asyncio
async def test_missing_workspace_membership_returns_error(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Users without a membership should receive a 403 when resolving workspace context."""

    orphan = seed_identity["orphan"]
    token = await _login(async_client, orphan["email"], orphan["password"])

    workspace_id = seed_identity["workspace_id"]
    response = await async_client.get(
        f"/workspaces/{workspace_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_without_membership_receives_error(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Application administrators should not gain workspace access implicitly."""

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])

    workspace_id = seed_identity["workspace_id"]
    response = await async_client.get(
        f"/workspaces/{workspace_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_permission_required_for_members_route(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Lacking the required permission should return 403."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        f"/workspaces/{seed_identity['workspace_id']}/members",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_members_route_allows_workspace_owner(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Workspace owners with the permission should succeed."""

    workspace_owner = seed_identity["workspace_owner"]
    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    response = await async_client.get(
        f"/workspaces/{seed_identity['workspace_id']}/members",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] is True
    assert payload["message"] == "Access granted"


@pytest.mark.asyncio
async def test_members_route_allows_member_with_manage_permission(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Members granted manage permission should receive read access automatically."""

    member_with_manage = seed_identity["member_with_manage"]
    token = await _login(
        async_client,
        member_with_manage["email"],
        member_with_manage["password"],
    )

    response = await async_client.get(
        f"/workspaces/{seed_identity['workspace_id']}/members",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] is True
    assert payload["message"] == "Access granted"


@pytest.mark.asyncio
async def test_list_workspaces_orders_default_first(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Workspace listings should return the default membership first."""

    member_with_manage = seed_identity["member_with_manage"]
    token = await _login(
        async_client,
        member_with_manage["email"],
        member_with_manage["password"],
    )

    response = await async_client.get(
        "/workspaces",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 2
    assert payload[0]["workspace_id"] == seed_identity["workspace_id"]
    assert payload[1]["workspace_id"] == seed_identity["secondary_workspace_id"]


@pytest.mark.asyncio
async def test_workspace_owner_can_add_member_with_role(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Workspace owners should be able to add users to their workspace with a chosen role."""

    workspace_owner = seed_identity["workspace_owner"]
    invitee = seed_identity["invitee"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    response = await async_client.post(
        f"/workspaces/{workspace_id}/members",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={"user_id": invitee["id"], "role": WorkspaceRole.OWNER.value},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["workspace_id"] == workspace_id
    assert payload["role"] == WorkspaceRole.OWNER.value
    assert payload["user"]["user_id"] == invitee["id"]
    permissions = set(payload.get("permissions", []))
    assert "workspace:members:manage" in permissions

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        membership = await session.get(
            WorkspaceMembership, payload["workspace_membership_id"]
        )
        assert membership is not None
        assert membership.workspace_id == workspace_id
        assert membership.user_id == invitee["id"]
        assert membership.role is WorkspaceRole.OWNER


@pytest.mark.asyncio
async def test_workspace_member_payload_requires_user_id(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """FastAPI should surface validation errors when required fields are missing."""

    workspace_owner = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    response = await async_client.post(
        f"/workspaces/{workspace_id}/members",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={},
    )

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    missing_fields = {entry["loc"][-1] for entry in detail}
    assert "user_id" in missing_fields


@pytest.mark.asyncio
async def test_manage_permission_required_for_member_addition(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Members without manage permission should not be able to add other users."""

    member = seed_identity["member"]
    invitee = seed_identity["invitee"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.post(
        f"/workspaces/{workspace_id}/members",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={"user_id": invitee["id"], "role": WorkspaceRole.MEMBER.value},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_member_returns_conflict(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Adding the same user twice should surface a conflict."""

    workspace_owner = seed_identity["workspace_owner"]
    invitee = seed_identity["invitee"]
    workspace_id = seed_identity["workspace_id"]
    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    first_response = await async_client.post(
        f"/workspaces/{workspace_id}/members",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={"user_id": invitee["id"], "role": WorkspaceRole.MEMBER.value},
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await async_client.post(
        f"/workspaces/{workspace_id}/members",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={"user_id": invitee["id"], "role": WorkspaceRole.OWNER.value},
    )
    assert second_response.status_code == 409
