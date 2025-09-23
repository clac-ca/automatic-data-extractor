"""User route coverage."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_list_users_requires_admin(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Non-admins should receive a 403 when listing users."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        "/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_admin_success(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Administrators should see all registered users."""

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])

    response = await async_client.get(
        "/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    emails = {item["email"] for item in data}
    expected = {
        seed_identity["admin"]["email"],
        seed_identity["workspace_owner"]["email"],
        seed_identity["member"]["email"],
        seed_identity["member_with_manage"]["email"],
        seed_identity["orphan"]["email"],
        seed_identity["invitee"]["email"],
    }
    assert expected.issubset(emails)
