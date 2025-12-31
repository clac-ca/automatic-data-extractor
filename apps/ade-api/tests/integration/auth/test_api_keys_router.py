"""Integration tests for API key routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.utils import login

pytestmark = pytest.mark.asyncio


async def _auth_headers(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, str]:
    token, _ = await login(client, email=email, password=password)
    return {"Authorization": f"Bearer {token}"}


async def test_admin_can_issue_api_key_for_user(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Admin endpoint should issue keys for a target user."""

    admin = seed_identity.admin
    target = seed_identity.member
    headers = await _auth_headers(
        async_client,
        email=admin.email,
        password=admin.password,
    )

    response = await async_client.post(
        f"/api/v1/users/{target.id}/api-keys",
        headers=headers,
        json={
            "name": "Integration key",
            "expires_in_days": 30,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["user_id"] == str(target.id)
    assert payload["secret"].startswith(f"{payload['prefix']}.")

    listing = await async_client.get(
        f"/api/v1/users/{target.id}/api-keys",
        headers=headers,
    )
    assert listing.status_code == 200, listing.text
    summary = listing.json()["items"][0]
    assert summary["id"] == payload["id"]
    assert summary["prefix"] == payload["prefix"]
    assert "secret" not in summary


async def test_me_api_keys_include_revoked_and_paginate(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Self-service listing should honor include_revoked and pagination params."""

    member = seed_identity.member
    headers = await _auth_headers(
        async_client,
        email=member.email,
        password=member.password,
    )

    first = await async_client.post(
        "/api/v1/users/me/api-keys",
        headers=headers,
        json={"name": "First key"},
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    second = await async_client.post(
        "/api/v1/users/me/api-keys",
        headers=headers,
        json={"name": "Second key"},
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]

    revoke = await async_client.delete(
        f"/api/v1/users/me/api-keys/{first_id}",
        headers=headers,
    )
    assert revoke.status_code == 204, revoke.text

    # Idempotent revoke should still return 204 when already revoked.
    revoke_repeat = await async_client.delete(
        f"/api/v1/users/me/api-keys/{first_id}",
        headers=headers,
    )
    assert revoke_repeat.status_code == 204, revoke_repeat.text

    active_response = await async_client.get(
        "/api/v1/users/me/api-keys",
        headers=headers,
    )
    assert active_response.status_code == 200, active_response.text
    active_payload = active_response.json()
    active_ids = {item["id"] for item in active_payload["items"]}
    assert first_id not in active_ids
    assert second_id in active_ids
    assert all(item["revoked_at"] is None for item in active_payload["items"])

    all_response = await async_client.get(
        "/api/v1/users/me/api-keys",
        headers=headers,
        params={"include_revoked": True},
    )
    assert all_response.status_code == 200, all_response.text
    all_payload = all_response.json()
    all_ids = {item["id"] for item in all_payload["items"]}
    assert {first_id, second_id}.issubset(all_ids)

    paged = await async_client.get(
        "/api/v1/users/me/api-keys",
        headers=headers,
        params={"include_revoked": True, "page_size": 1},
    )
    assert paged.status_code == 200, paged.text
    paged_payload = paged.json()
    assert paged_payload["page"] == 1
    assert paged_payload["page_size"] == 1
    assert paged_payload["has_next"] is True
