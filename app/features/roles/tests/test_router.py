from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/auth/session", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get("ade_session")
    assert token, "Session cookie missing"
    return token


@pytest.mark.asyncio
async def test_permission_catalog_workspace(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    owner = seed_identity["workspace_owner"]
    token = await _login(async_client, owner["email"], owner["password"])

    response = await async_client.get(
        "/api/permissions",
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
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        "/api/permissions",
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
    token = await _login(async_client, admin["email"], admin["password"])

    response = await async_client.get(
        "/api/permissions",
        params={"scope": "global"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(entry["key"] == "Roles.Read.All" for entry in payload)
