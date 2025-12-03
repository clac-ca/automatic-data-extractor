"""User router tests."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.utils import login

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

    emails: set[str] = set()
    page = 1
    while True:
        response = await async_client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            params={"page": page, "page_size": 100},
        )
        assert response.status_code == 200
        data = response.json()
        emails.update(item["email"] for item in data["items"])
        if not data["has_next"]:
            break
        page += 1
        assert page < 10, "unexpectedly large number of pages"
    expected = {
        seed_identity["admin"]["email"],
        seed_identity["workspace_owner"]["email"],
        seed_identity["member"]["email"],
        seed_identity["member_with_manage"]["email"],
        seed_identity["orphan"]["email"],
        seed_identity["invitee"]["email"],
    }
    assert expected.issubset(emails)


async def test_get_user_requires_admin(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Non-admins should not be able to fetch user details."""

    member = seed_identity["member"]
    target = seed_identity["admin"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.get(
        f"/api/v1/users/{target['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_get_user_admin_success(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Administrators should retrieve individual user profiles."""

    admin = seed_identity["admin"]
    target = seed_identity["member"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.get(
        f"/api/v1/users/{target['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(target["id"])
    assert data["email"] == target["email"]
    assert data["is_active"] is True
    assert "global-user" in data["roles"]


async def test_get_user_admin_not_found(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Administrators should receive 404 for unknown users."""

    admin = seed_identity["admin"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.get(
        f"/api/v1/users/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


async def test_update_user_requires_admin(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Non-admins should not be able to mutate user records."""

    member = seed_identity["member"]
    target = seed_identity["invitee"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.patch(
        f"/api/v1/users/{target['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Blocked"},
    )

    assert response.status_code == 403


async def test_update_user_admin_success(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Administrators should be able to update user status and metadata."""

    admin = seed_identity["admin"]
    target = seed_identity["invitee"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.patch(
        f"/api/v1/users/{target['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": " Updated Invitee ", "is_active": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Updated Invitee"
    assert data["is_active"] is False

    confirm = await async_client.get(
        f"/api/v1/users/{target['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    confirm_data = confirm.json()
    assert confirm_data["display_name"] == "Updated Invitee"
    assert confirm_data["is_active"] is False


async def test_get_user_requires_admin(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Non-admins should be blocked from reading user profiles."""

    member = seed_identity["member"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.get(
        f"/api/v1/users/{seed_identity['admin']['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_get_user_admin_success(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Administrators should be able to fetch a single user."""

    admin = seed_identity["admin"]
    member = seed_identity["member"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.get(
        f"/api/v1/users/{member['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(member["id"])
    assert payload["email"] == member["email"]
    assert payload["is_active"] is True
    assert "global-user" in payload["roles"]
    assert isinstance(payload["permissions"], list)


async def test_update_user_requires_admin(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Non-admins should not be able to update user profiles."""

    member = seed_identity["member"]
    token, _ = await login(async_client, email=member["email"], password=member["password"])

    response = await async_client.patch(
        f"/api/v1/users/{seed_identity['invitee']['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Unauthorized"},
    )
    assert response.status_code == 403


async def test_update_user_admin_success(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Administrators should be able to mutate display name and active state."""

    admin = seed_identity["admin"]
    target = seed_identity["invitee"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.patch(
        f"/api/v1/users/{target['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Updated Invitee", "is_active": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "Updated Invitee"
    assert payload["is_active"] is False


async def test_update_user_rejects_empty_payload(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """PATCH without fields should be rejected."""

    admin = seed_identity["admin"]
    target = seed_identity["member"]
    token, _ = await login(async_client, email=admin["email"], password=admin["password"])

    response = await async_client.patch(
        f"/api/v1/users/{target['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 422
