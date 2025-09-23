"""Authentication endpoint tests."""

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
    payload = response.json()
    return payload["access_token"]


@pytest.mark.asyncio
async def test_issue_token_and_me(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    """Users should obtain tokens and fetch their profile."""

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])

    response = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == admin["email"]
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_invalid_credentials_rejected(async_client: AsyncClient) -> None:
    """Submitting an unknown user should produce 401."""

    response = await async_client.post(
        "/auth/token",
        data={"username": "missing@example.com", "password": "nope"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_profile_requires_authentication(async_client: AsyncClient) -> None:
    """GET /auth/me should require a valid token."""

    response = await async_client.get("/auth/me")
    assert response.status_code == 401
