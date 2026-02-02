"""Configuration archival tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.configs.helpers import auth_headers, create_from_template

pytestmark = pytest.mark.asyncio


async def test_archive_configuration_sets_archived(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    record = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    publish = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/publish",
        headers=headers,
        json=None,
    )
    assert publish.status_code == 200, publish.text

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/archive",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"


async def test_archive_returns_409_when_configuration_not_active(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    record = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/archive",
        headers=headers,
    )
    assert response.status_code == 409
    assert "active" in (response.json().get("detail") or "").lower()
