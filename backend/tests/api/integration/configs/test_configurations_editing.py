"""Configuration editing guards."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.configs.helpers import auth_headers, create_from_template

pytestmark = pytest.mark.asyncio


async def test_editing_non_draft_rejected(
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
    base_url = f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}"
    publish = await async_client.post(
        f"{base_url}/publish",
        headers=headers,
        json=None,
    )
    assert publish.status_code == 200, publish.text
    put_headers = dict(headers)
    put_headers["If-None-Match"] = "*"
    put_headers["Content-Type"] = "application/octet-stream"
    resp = await async_client.put(
        f"{base_url}/files/assets/blocked.txt?parents=1",
        headers=put_headers,
        content=b"forbidden",
    )
    assert resp.status_code == 409
