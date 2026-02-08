"""Helper functions shared across tests."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from ade_api.settings import get_settings

async def login(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> tuple[str, dict[str, Any]]:
    """Authenticate and mint a user API key, returning ``(api_key_secret, payload)``."""

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text

    settings = get_settings()
    csrf_cookie = client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie, "CSRF cookie missing after login"

    key_response = await client.post(
        "/api/v1/users/me/apikeys",
        json={"name": "test-login-key"},
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert key_response.status_code == 201, key_response.text
    payload = key_response.json()
    token = payload.get("secret")
    assert token, "API key secret missing"
    return token, payload


__all__ = ["login"]
