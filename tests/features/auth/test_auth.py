"""Authentication endpoint tests."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app import reload_settings
from app.features.auth.service import (
    SSO_STATE_COOKIE,
    AuthService,
    OIDCProviderMetadata,
)

CSRF_COOKIE = "ade_csrf"


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token, "CSRF cookie not set"
    return {"X-CSRF-Token": token}


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_session_and_me(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Users should create sessions and fetch their profile."""

    admin = seed_identity["admin"]
    payload = await _login(async_client, admin["email"], admin["password"])
    assert payload["user"]["email"] == admin["email"]

    response = await async_client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == admin["email"]
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_login_sets_csrf_cookie_and_header(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Login responses should surface CSRF metadata for the frontend."""

    admin = seed_identity["admin"]
    response = await async_client.post(
        "/api/auth/login",
        json={"email": admin["email"], "password": admin["password"]},
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("X-CSRF-Token")
    assert async_client.cookies.get(CSRF_COOKIE)


@pytest.mark.asyncio
async def test_invalid_credentials_rejected(async_client: AsyncClient) -> None:
    """Submitting an unknown user should produce 401."""

    response = await async_client.post(
        "/api/auth/login",
        json={"email": "missing@example.test", "password": "nope"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("username", "password", "expected_messages"),
    [
        ("", "secret", {"Email must not be empty"}),
        ("   ", "secret", {"Email must not be empty"}),
        ("user@example.test", "   ", {"Password must not be empty"}),
        ("not-an-email", "secret", {"The email address is not valid"}),
    ],
)
async def test_create_session_validation_errors(
    async_client: AsyncClient,
    username: str,
    password: str,
    expected_messages: set[str],
) -> None:
    """Invalid credentials should surface as 422 validation errors."""

    response = await async_client.post(
        "/api/auth/login",
        json={"email": username, "password": password},
    )
    assert response.status_code == 422, response.text

    payload = response.json()
    assert isinstance(payload.get("detail"), list)
    messages = {error.get("msg", "") for error in payload["detail"]}
    for expected in expected_messages:
        assert any(expected in message for message in messages)


@pytest.mark.asyncio
async def test_profile_requires_authentication(async_client: AsyncClient) -> None:
    """GET /auth/me should require a valid session."""

    response = await async_client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_requires_csrf_header(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """POST /auth/refresh should enforce the double submit cookie check."""

    admin = seed_identity["admin"]
    await _login(async_client, admin["email"], admin["password"])

    missing = await async_client.post("/api/auth/refresh")
    assert missing.status_code == 403

    rotated = await async_client.post(
        "/api/auth/refresh",
        headers=_csrf_headers(async_client),
    )
    assert rotated.status_code == 200, rotated.text
    payload = rotated.json()
    assert payload["user"]["email"] == admin["email"]


@pytest.mark.asyncio
async def test_api_key_rotation_and_revocation(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Issued API keys should support rotation and revocation."""

    admin = seed_identity["admin"]
    await _login(async_client, admin["email"], admin["password"])

    first = await async_client.post(
        "/api/auth/api-keys",
        json={"email": admin["email"]},
        headers=_csrf_headers(async_client),
    )
    assert first.status_code == 201, first.text
    first_key = first.json()["api_key"]
    first_prefix, _ = first_key.split(".", 1)

    second = await async_client.post(
        "/api/auth/api-keys",
        json={"email": admin["email"]},
        headers=_csrf_headers(async_client),
    )
    assert second.status_code == 201, second.text
    second_key = second.json()["api_key"]
    second_prefix, _ = second_key.split(".", 1)

    listing = await async_client.get("/api/auth/api-keys")
    assert listing.status_code == 200
    records = listing.json()
    assert len(records) == 2
    record_lookup = {record["token_prefix"]: record for record in records}
    first_record = record_lookup[first_prefix]
    second_record = record_lookup[second_prefix]
    assert first_record["principal_type"] == "user"
    assert first_record["principal_label"] == admin["email"]
    assert second_record["principal_type"] == "user"
    assert second_record["principal_label"] == admin["email"]

    async_client.cookies.clear()
    response = await async_client.get("/api/auth/me", headers={"X-API-Key": first_key})
    assert response.status_code == 200
    response = await async_client.get("/api/auth/me", headers={"X-API-Key": second_key})
    assert response.status_code == 200

    await _login(async_client, admin["email"], admin["password"])
    revoke = await async_client.delete(
        f"/api/auth/api-keys/{first_record['api_key_id']}",
        headers=_csrf_headers(async_client),
    )
    assert revoke.status_code == 204

    async_client.cookies.clear()
    denied = await async_client.get("/api/auth/me", headers={"X-API-Key": first_key})
    assert denied.status_code == 401
    allowed = await async_client.get("/api/auth/me", headers={"X-API-Key": second_key})
    assert allowed.status_code == 200

    await _login(async_client, admin["email"], admin["password"])
    remaining = await async_client.get("/api/auth/api-keys")
    payload = remaining.json()
    assert [record["token_prefix"] for record in payload] == [second_prefix]
    assert payload[0]["principal_type"] == "user"
    assert payload[0]["principal_label"] == admin["email"]


@pytest.mark.asyncio
async def test_api_key_payload_requires_target(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """FastAPI should surface validation errors when the payload is empty."""

    admin = seed_identity["admin"]
    await _login(async_client, admin["email"], admin["password"])

    response = await async_client.post(
        "/api/auth/api-keys",
        json={},
        headers=_csrf_headers(async_client),
    )

    assert response.status_code == 422, response.text
    body = response.json()
    assert isinstance(body.get("detail"), list)
    messages = {error.get("msg", "") for error in body["detail"]}
    assert any("user_id or email is required" in message for message in messages)


@pytest.mark.asyncio
async def test_service_account_api_keys(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Administrators should issue API keys to service accounts."""

    admin = seed_identity["admin"]
    service_account = seed_identity["service_account"]
    inactive_service_account = seed_identity["inactive_service_account"]
    await _login(async_client, admin["email"], admin["password"])

    issued = await async_client.post(
        "/api/auth/api-keys",
        json={"user_id": service_account["id"]},
        headers=_csrf_headers(async_client),
    )
    assert issued.status_code == 201, issued.text
    data = issued.json()
    assert data["principal_type"] == "service_account"
    assert data["principal_id"] == service_account["id"]
    assert data["principal_label"] == service_account["display_name"]
    api_key = data["api_key"]

    listing = await async_client.get("/api/auth/api-keys")
    assert listing.status_code == 200
    records = listing.json()
    lookup = {record["token_prefix"]: record for record in records}
    prefix, _ = api_key.split(".", 1)
    record = lookup[prefix]
    assert record["principal_type"] == "service_account"
    assert record["principal_id"] == service_account["id"]
    assert record["principal_label"] == service_account["display_name"]

    async_client.cookies.clear()
    denied = await async_client.get("/api/auth/me", headers={"X-API-Key": api_key})
    assert denied.status_code == 403

    await _login(async_client, admin["email"], admin["password"])
    inactive = await async_client.post(
        "/api/auth/api-keys",
        json={"user_id": inactive_service_account["id"]},
        headers=_csrf_headers(async_client),
    )
    assert inactive.status_code == 400


@pytest.mark.asyncio
async def test_service_account_password_login_blocked(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Password login should return 403 for service accounts."""

    service_account = seed_identity["service_account"]
    response = await async_client.post(
        "/api/auth/login",
        json={"email": service_account["email"], "password": "irrelevant"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_logout_clears_cookies(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """POST /auth/logout should remove authentication cookies."""

    admin = seed_identity["admin"]
    await _login(async_client, admin["email"], admin["password"])

    forbidden = await async_client.post("/api/auth/logout")
    assert forbidden.status_code == 403

    response = await async_client.post(
        "/api/auth/logout",
        headers=_csrf_headers(async_client),
    )
    assert response.status_code == 204
    assert async_client.cookies.get("ade_session") is None
    assert async_client.cookies.get("ade_refresh") is None


@pytest.mark.asyncio
async def test_sso_callback_rejects_state_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """The SSO callback should reject mismatched state tokens."""

    monkeypatch.setenv("ADE_OIDC_ENABLED", "true")
    monkeypatch.setenv("ADE_OIDC_CLIENT_ID", "demo-client")
    monkeypatch.setenv("ADE_OIDC_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ADE_OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv(
        "ADE_OIDC_REDIRECT_URL", "https://ade.example.com/auth/sso/callback"
    )
    monkeypatch.setenv(
        "ADE_OIDC_SCOPES", '["openid","email","profile"]'
    )
    reload_settings()
    override_app_settings()

    metadata = OIDCProviderMetadata(
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        jwks_uri="https://issuer.example.com/jwks",
    )

    async def fake_metadata(self: AuthService) -> OIDCProviderMetadata:
        return metadata

    monkeypatch.setattr(AuthService, "_get_oidc_metadata", fake_metadata)

    login = await async_client.get("/api/auth/sso/login", follow_redirects=False)
    assert login.status_code in (302, 307)
    assert SSO_STATE_COOKIE in login.cookies
    state_cookie = login.cookies[SSO_STATE_COOKIE]

    callback = await async_client.get(
        "/api/auth/sso/callback",
        params={"code": "auth-code", "state": "wrong-state"},
        cookies={SSO_STATE_COOKIE: state_cookie},
    )
    assert callback.status_code == 400

