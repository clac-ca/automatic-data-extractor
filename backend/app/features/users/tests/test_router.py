"""User router tests."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from backend.app.tests.utils import login


pytestmark = pytest.mark.asyncio


async def test_list_users_requires_admin(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Non-admins should receive a 403 when listing users."""

    member = seed_identity["member"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

async def test_list_users_admin_success(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Administrators should see all registered users."""

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.get(
        "/api/v1/users",
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
