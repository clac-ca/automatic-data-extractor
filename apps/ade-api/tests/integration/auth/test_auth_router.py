"""Authentication endpoint smoke tests for the new auth module."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from ade_api.settings import get_settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_login_and_refresh(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Password login should return tokens and allow refresh."""

    admin = seed_identity["admin"]
    access_token, payload = await login(
        async_client,
        email=admin["email"],
        password=admin["password"],
    )
    assert payload["token_type"] == "bearer"
    assert payload["refresh_token"]
    assert payload["expires_in"] > 0
    assert payload["refresh_expires_in"] > 0

    refresh = await async_client.post(
        "/api/v1/auth/session/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    refreshed = refresh.json()
    assert refreshed["access_token"]
    assert refreshed["token_type"] == "bearer"


async def test_refresh_prefers_body_over_cookie(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Body-supplied refresh tokens should override cookies."""

    admin = seed_identity["admin"]
    _, payload = await login(
        async_client,
        email=admin["email"],
        password=admin["password"],
    )

    refresh_cookie = get_settings().session_refresh_cookie_name
    async_client.cookies.set(refresh_cookie, "stale-cookie-token")

    response = await async_client.post(
        "/api/v1/auth/session/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["access_token"]
    assert data["refresh_token"]


async def test_refresh_falls_back_to_cookie(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Requests without a body should refresh using the cookie token."""

    admin = seed_identity["admin"]
    _, payload = await login(
        async_client,
        email=admin["email"],
        password=admin["password"],
    )

    refresh_cookie = get_settings().session_refresh_cookie_name
    async_client.cookies.set(refresh_cookie, payload["refresh_token"])

    response = await async_client.post("/api/v1/auth/session/refresh")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["access_token"]
    assert data["refresh_token"]


async def test_invalid_credentials_rejected(async_client: AsyncClient) -> None:
    """Bad credentials should return 401."""

    response = await async_client.post(
        "/api/v1/auth/session",
        json={"email": "missing@example.com", "password": "nope"},
    )
    assert response.status_code == 401


async def test_setup_status_when_users_exist(async_client: AsyncClient) -> None:
    """When users are present, setup should be marked complete."""

    response = await async_client.get("/api/v1/auth/setup")
    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_setup"] is False
    assert payload["has_users"] is True


async def test_setup_conflict_when_users_exist(async_client: AsyncClient) -> None:
    """POST /auth/setup should return 409 once users exist."""

    response = await async_client.post(
        "/api/v1/auth/setup",
        json={
            "email": "first@example.com",
            "password": "password123!",
            "display_name": "First Admin",
        },
    )
    assert response.status_code == 409


async def test_list_auth_providers_default_password_only(
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """Provider discovery should expose password login when SSO is disabled."""

    override_app_settings(auth_force_sso=False, oidc_enabled=False)
    response = await async_client.get("/api/v1/auth/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["force_sso"] is False
    assert payload["providers"] == [
        {
            "id": "password",
            "label": "Email & password",
            "type": "password",
            "start_url": "/api/v1/auth/session",
            "icon_url": None,
        }
    ]


async def test_list_auth_providers_force_sso(
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """When SSO is forced and enabled, only the SSO provider should appear."""

    override_app_settings(
        auth_force_sso=True,
        oidc_enabled=True,
        oidc_client_id="demo-client",
        oidc_client_secret=SecretStr("demo-secret"),
        oidc_issuer="https://issuer.example.com",
        oidc_redirect_url="https://app.example.com/auth/callback",
    )
    response = await async_client.get("/api/v1/auth/providers")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["force_sso"] is True
    assert payload["providers"] == [
        {
            "id": "sso",
            "label": "Single sign-on",
            "type": "oidc",
            "start_url": "/api/v1/auth/sso/sso/authorize",
            "icon_url": None,
        }
    ]


async def test_logout_returns_no_content(async_client: AsyncClient) -> None:
    """Logout should be a no-op but return 204."""

    response = await async_client.delete("/api/v1/auth/session")
    assert response.status_code == 204
