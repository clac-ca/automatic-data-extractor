"""Helper functions shared across tests."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from httpx import AsyncClient

from ade_api.features.api_keys.service import ApiKeyService
from ade_api.settings import get_settings


def _resolve_test_app(client: AsyncClient):
    transport = getattr(client, "_transport", None)
    return getattr(transport, "app", None)


async def _mint_api_key_directly(
    client: AsyncClient,
    *,
    user_id: UUID,
) -> tuple[str, dict[str, Any]]:
    app = _resolve_test_app(client)
    assert app is not None, "Unable to resolve ASGI app from test client."

    db_sessionmaker = getattr(app.state, "db_sessionmaker", None)
    assert db_sessionmaker is not None, "Test DB sessionmaker was not attached to app.state."

    settings = getattr(app.state, "settings", None) or get_settings()
    session = db_sessionmaker()
    try:
        service = ApiKeyService(session=session, settings=settings)
        result = service.create_for_user(
            user_id=user_id,
            name="test-login-key",
            expires_in_days=None,
        )
        session.commit()
        payload = {
            "id": str(result.api_key.id),
            "prefix": result.api_key.prefix,
            "secret": result.secret,
        }
        return result.secret, payload
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


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
    if key_response.status_code == 201:
        payload = key_response.json()
        token = payload.get("secret")
        assert token, "API key secret missing"
        return token, payload

    assert key_response.status_code == 403, key_response.text

    me_response = await client.get("/api/v1/me")
    assert me_response.status_code == 200, me_response.text
    me_payload = me_response.json()
    user_id_raw = me_payload.get("id")
    assert isinstance(user_id_raw, str) and user_id_raw.strip(), "User id missing from /api/v1/me response."
    return await _mint_api_key_directly(client, user_id=UUID(user_id_raw))


__all__ = ["login"]
