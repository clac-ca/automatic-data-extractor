"""User router tests."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_list_users_requires_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Non-admins should receive a 403 when listing users."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_users_admin_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should see all registered users."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    emails: set[str] = set()
    cursor: str | None = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        response = await async_client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        assert response.status_code == 200
        data = response.json()
        emails.update(item["email"] for item in data["items"])
        if not data["meta"]["hasMore"]:
            break
        cursor = data["meta"]["nextCursor"]
        assert cursor is not None
    expected = {
        seed_identity.admin.email,
        seed_identity.workspace_owner.email,
        seed_identity.member.email,
        seed_identity.member_with_manage.email,
        seed_identity.orphan.email,
    }
    assert expected.issubset(emails)


async def test_get_user_requires_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Non-admins should not be able to fetch user details."""

    member = seed_identity.member
    target = seed_identity.admin
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_get_user_admin_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should retrieve individual user profiles."""

    admin = seed_identity.admin
    target = seed_identity.member
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(target.id)
    assert data["email"] == target.email
    assert data["is_active"] is True
    assert "global-user" in data["roles"]
    assert isinstance(data["permissions"], list)


async def test_get_user_admin_not_found(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should receive 404 for unknown users."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        f"/api/v1/users/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


async def test_update_user_requires_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Non-admins should not be able to mutate user records."""

    member = seed_identity.member
    target = seed_identity.orphan
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.patch(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Blocked"},
    )

    assert response.status_code == 403


async def test_update_user_admin_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should be able to update user status and metadata."""

    admin = seed_identity.admin
    target = seed_identity.orphan
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.patch(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": " Updated User ", "is_active": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Updated User"
    assert data["is_active"] is False

    confirm = await async_client.get(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    confirm_data = confirm.json()
    assert confirm_data["display_name"] == "Updated User"
    assert confirm_data["is_active"] is False


async def test_update_user_rejects_empty_payload(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """PATCH without fields should be rejected."""

    admin = seed_identity.admin
    target = seed_identity.member
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.patch(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 422


async def test_deactivate_user_revokes_api_keys(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Deactivation should set is_active false and revoke all owned API keys."""

    admin = seed_identity.admin
    target = seed_identity.member
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)

    create_key = await async_client.post(
        f"/api/v1/users/{target.id}/apikeys",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Target key"},
    )
    assert create_key.status_code == 201, create_key.text
    secret = create_key.json()["secret"]

    preflight = await async_client.get(
        "/api/v1/me/bootstrap",
        headers={"X-API-Key": secret},
    )
    assert preflight.status_code == 200, preflight.text

    deactivate = await async_client.post(
        f"/api/v1/users/{target.id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deactivate.status_code == 200, deactivate.text
    payload = deactivate.json()
    assert payload["is_active"] is False

    revoked_filters = json.dumps([{"id": "revokedAt", "operator": "isNotEmpty"}])
    key_list = await async_client.get(
        f"/api/v1/users/{target.id}/apikeys",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"filters": revoked_filters},
    )
    assert key_list.status_code == 200, key_list.text
    records = key_list.json()["items"]
    assert records
    assert all(record["revoked_at"] is not None for record in records)

    denied = await async_client.get(
        "/api/v1/me/bootstrap",
        headers={"X-API-Key": secret},
    )
    assert denied.status_code == 401


async def test_deactivate_user_blocks_self(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Users should not be able to deactivate themselves."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.post(
        f"/api/v1/users/{admin.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
