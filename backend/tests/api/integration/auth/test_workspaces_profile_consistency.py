from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_global_admin_workspace_profile_is_consistent_after_create(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    token, _ = await login(
        async_client,
        email=seed_identity.admin.email,
        password=seed_identity.admin.password,
    )
    headers = {"X-API-Key": token}
    slug = f"consistency-{uuid4().hex[:8]}"

    create_response = await async_client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Consistency Workspace", "slug": slug},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    workspace_id = created["id"]

    assert created["roles"] == ["workspace-owner"]
    assert created["is_default"] is True

    list_response = await async_client.get(
        "/api/v1/workspaces",
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    listed_items = list_response.json().get("items", [])
    listed = next((item for item in listed_items if item["id"] == workspace_id), None)
    assert listed is not None
    assert listed["roles"] == created["roles"]
    assert listed["is_default"] == created["is_default"]

    read_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}",
        headers=headers,
    )
    assert read_response.status_code == 200, read_response.text
    read = read_response.json()
    assert read["roles"] == created["roles"]
    assert read["is_default"] == created["is_default"]
