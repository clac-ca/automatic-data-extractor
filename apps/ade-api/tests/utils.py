"""Helper functions shared across tests."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

async def login(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> tuple[str, dict[str, Any]]:
    """Authenticate ``email``/``password`` returning (session_cookie, payload)."""

    response = await client.post(
        "/api/v1/auth/session",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    token = payload.get("access_token")
    assert token, "Access token missing"
    return token, payload


__all__ = ["login"]
