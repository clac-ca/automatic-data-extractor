"""Auth-disabled mode should provision a dev admin user with full permissions."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_auth_disabled_injects_global_admin_permissions(
    async_client: AsyncClient,
    override_app_settings,
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
    assert set(payload["user"]["roles"]) == set(payload["roles"])

    permissions = set(payload.get("permissions") or [])
    assert {"workspaces.create", "workspaces.manage_all"}.issubset(permissions)
    assert set(payload["user"]["permissions"]) == permissions


async def test_auth_disabled_effective_permissions_payload(
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    override_app_settings(
        auth_disabled=True,
        auth_disabled_user_email="dev-auth-disabled@example.com",
    )

    response = await async_client.get("/api/v1/me/permissions")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert set(payload.keys()) == {"global", "workspaces"}
    global_permissions = set(payload["global"])
    assert {"workspaces.create", "workspaces.manage_all"}.issubset(global_permissions)
    assert isinstance(payload["workspaces"], dict)
    for value in payload["workspaces"].values():
        assert isinstance(value, list)
