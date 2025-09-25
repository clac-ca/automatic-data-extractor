"""Workspace endpoint coverage."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.api.db.session import get_sessionmaker
from backend.api.modules.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _create_workspace(
    client: AsyncClient,
    admin: dict[str, Any],
    *,
    owner_user_id: str | None = None,
    name: str | None = None,
    slug: str | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = await _login(client, admin["email"], admin["password"])
    workspace_name = name or f"Workspace {uuid4().hex[:8]}"
    payload: dict[str, Any] = {"name": workspace_name}
    if slug is not None:
        payload["slug"] = slug
    if owner_user_id is not None:
        payload["owner_user_id"] = owner_user_id
    if settings is not None:
        payload["settings"] = settings

    response = await client.post(
        "/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


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
async def test_admin_without_membership_can_access_workspace(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Global administrators should be able to resolve workspace context."""

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])

    workspace_id = seed_identity["workspace_id"]
    response = await async_client.get(
        f"/workspaces/{workspace_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    workspace_payload = payload["workspace"]
    assert workspace_payload["workspace_id"] == workspace_id
    assert workspace_payload["role"] == WorkspaceRole.OWNER.value
    permissions = set(workspace_payload.get("permissions", []))
    assert "workspace:settings:manage" in permissions


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
    assert isinstance(payload, list)
    owner_ids = {member["user"]["user_id"] for member in payload}
    assert workspace_owner["id"] in owner_ids


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
    assert isinstance(payload, list)
    member_ids = {member["user"]["user_id"] for member in payload}
    assert seed_identity["member_with_manage"]["id"] in member_ids


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

    admin = seed_identity["admin"]
    workspace_owner = seed_identity["workspace_owner"]
    invitee = seed_identity["invitee"]
    created = await _create_workspace(
        async_client,
        admin,
        owner_user_id=workspace_owner["id"],
    )
    workspace_id = created["workspace_id"]
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

    admin = seed_identity["admin"]
    workspace_owner = seed_identity["workspace_owner"]
    invitee = seed_identity["invitee"]
    created = await _create_workspace(
        async_client,
        admin,
        owner_user_id=workspace_owner["id"],
    )
    workspace_id = created["workspace_id"]
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


@pytest.mark.asyncio
async def test_admin_can_create_workspace_with_owner(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Global administrators should create workspaces and assign owners."""

    admin = seed_identity["admin"]
    workspace_owner = seed_identity["workspace_owner"]
    name = "Northwind Research"
    slug = "northwind-research"

    profile = await _create_workspace(
        async_client,
        admin,
        owner_user_id=workspace_owner["id"],
        name=name,
        slug=slug,
        settings={"region": "us-east"},
    )
    assert profile["name"] == name
    assert profile["slug"] == slug
    assert profile["role"] == WorkspaceRole.OWNER.value

    workspace_id = profile["workspace_id"]
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await session.get(Workspace, workspace_id)
        assert workspace is not None
        assert workspace.slug == slug
        assert workspace.settings == {"region": "us-east"}

        result = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == workspace_owner["id"],
            )
        )
        membership = result.scalar_one()
        assert membership.role is WorkspaceRole.OWNER


@pytest.mark.asyncio
async def test_admin_lists_all_workspaces(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Administrators should see every workspace regardless of membership."""

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])

    response = await async_client.get(
        "/workspaces",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    workspace_ids = {entry["workspace_id"] for entry in payload}
    assert seed_identity["workspace_id"] in workspace_ids
    assert seed_identity["secondary_workspace_id"] in workspace_ids
    assert all(entry["role"] == WorkspaceRole.OWNER.value for entry in payload)


@pytest.mark.asyncio
async def test_workspace_owner_can_update_metadata(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Workspace owners should update names, slugs, and settings."""

    admin = seed_identity["admin"]
    workspace_owner = seed_identity["workspace_owner"]
    created = await _create_workspace(
        async_client,
        admin,
        owner_user_id=workspace_owner["id"],
        name="Original Name",
    )
    workspace_id = created["workspace_id"]

    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    response = await async_client.patch(
        f"/workspaces/{workspace_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Updated Workspace",
            "slug": "updated-workspace",
            "settings": {"timezone": "utc"},
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["name"] == "Updated Workspace"
    assert payload["slug"] == "updated-workspace"

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await session.get(Workspace, workspace_id)
        assert workspace is not None
        assert workspace.slug == "updated-workspace"
        assert workspace.settings == {"timezone": "utc"}


@pytest.mark.asyncio
async def test_workspace_owner_can_delete_workspace(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Owners should remove workspaces they control."""

    admin = seed_identity["admin"]
    workspace_owner = seed_identity["workspace_owner"]
    created = await _create_workspace(
        async_client,
        admin,
        owner_user_id=workspace_owner["id"],
    )
    workspace_id = created["workspace_id"]

    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    response = await async_client.delete(
        f"/workspaces/{workspace_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] is True

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = await session.get(Workspace, workspace_id)
        assert workspace is None


@pytest.mark.asyncio
async def test_workspace_owner_can_update_member_role(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Owners should promote or demote workspace members."""

    admin = seed_identity["admin"]
    workspace_owner = seed_identity["workspace_owner"]
    invitee = seed_identity["invitee"]
    created = await _create_workspace(
        async_client,
        admin,
        owner_user_id=workspace_owner["id"],
    )
    workspace_id = created["workspace_id"]

    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    create_response = await async_client.post(
        f"/workspaces/{workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": invitee["id"], "role": WorkspaceRole.MEMBER.value},
    )
    assert create_response.status_code == 201, create_response.text
    membership_id = create_response.json()["workspace_membership_id"]

    update_response = await async_client.patch(
        f"/workspaces/{workspace_id}/members/{membership_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": WorkspaceRole.OWNER.value},
    )
    assert update_response.status_code == 200, update_response.text
    payload = update_response.json()
    assert payload["role"] == WorkspaceRole.OWNER.value

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        membership = await session.get(WorkspaceMembership, membership_id)
        assert membership is not None
        assert membership.role is WorkspaceRole.OWNER


@pytest.mark.asyncio
async def test_workspace_owner_can_remove_member(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Owners should remove members from their workspace."""

    admin = seed_identity["admin"]
    workspace_owner = seed_identity["workspace_owner"]
    invitee = seed_identity["invitee"]
    created = await _create_workspace(
        async_client,
        admin,
        owner_user_id=workspace_owner["id"],
    )
    workspace_id = created["workspace_id"]

    token = await _login(
        async_client,
        workspace_owner["email"],
        workspace_owner["password"],
    )

    create_response = await async_client.post(
        f"/workspaces/{workspace_id}/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": invitee["id"], "role": WorkspaceRole.MEMBER.value},
    )
    assert create_response.status_code == 201, create_response.text
    membership_id = create_response.json()["workspace_membership_id"]

    delete_response = await async_client.delete(
        f"/workspaces/{workspace_id}/members/{membership_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 200

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        membership = await session.get(WorkspaceMembership, membership_id)
        assert membership is None


@pytest.mark.asyncio
async def test_member_can_set_default_workspace(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Members should be able to change their default workspace selection."""

    member = seed_identity["member_with_manage"]
    token = await _login(async_client, member["email"], member["password"])

    secondary_workspace_id = seed_identity["secondary_workspace_id"]
    response = await async_client.post(
        f"/workspaces/{secondary_workspace_id}/default",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_id"] == secondary_workspace_id
    assert payload["is_default"] is True

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == member["id"],
                WorkspaceMembership.workspace_id == secondary_workspace_id,
            )
        )
        membership = result.scalar_one()
        assert membership.is_default is True

    # revert default to primary workspace to avoid affecting other tests
    revert = await async_client.post(
        f"/workspaces/{seed_identity['workspace_id']}/default",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revert.status_code == 200
