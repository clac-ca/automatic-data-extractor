"""Helper functions shared across tests."""

from __future__ import annotations

from typing import Any, Tuple

from httpx import AsyncClient

from apps.api.app.settings import get_settings

ADE_SESSION_COOKIE = get_settings().session_cookie_name


async def login(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> Tuple[str, dict[str, Any]]:
    """Authenticate ``email``/``password`` returning (session_cookie, payload)."""

    response = await client.post(
        "/api/v1/auth/session",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get(ADE_SESSION_COOKIE)
    assert token, "Session cookie missing"
    return token, response.json()


__all__ = ["login", "ADE_SESSION_COOKIE"]
