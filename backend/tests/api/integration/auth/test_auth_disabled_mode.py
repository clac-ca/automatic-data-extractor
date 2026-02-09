from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_auth_disabled_bootstrap_returns_dev_user(
    async_client: AsyncClient,
    override_app_settings,
    seed_identity,
) -> None:
    override_app_settings(
        auth_disabled=True,
        auth_disabled_user_email="dev-auth-disabled@example.com",
    )

    response = await async_client.get("/api/v1/me/bootstrap")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["email"] == "dev-auth-disabled@example.com"
    assert "global-admin" in payload["roles"]
    assert payload["workspaces"]
    workspace_ids = {item["id"] for item in payload["workspaces"]}
    assert str(seed_identity.workspace_id) in workspace_ids
    assert str(seed_identity.secondary_workspace_id) in workspace_ids
    preferred_workspace_id = payload["user"]["preferred_workspace_id"]
    assert isinstance(preferred_workspace_id, str)
    assert preferred_workspace_id in workspace_ids
