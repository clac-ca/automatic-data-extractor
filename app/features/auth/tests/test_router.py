"""Authentication endpoint tests."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app import get_settings, reload_settings
from app.db.session import get_sessionmaker
from app.features.auth.service import (
    SSO_STATE_COOKIE,
    AuthService,
    OIDCProviderMetadata,
)
from app.features.users.repository import UsersRepository

CSRF_COOKIE = "ade_csrf"


pytestmark = pytest.mark.asyncio


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token, "CSRF cookie not set"
    return {"X-CSRF-Token": token}


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/session",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_create_session_and_me(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Users should create sessions and fetch their profile."""

    admin = seed_identity["admin"]
    payload = await _login(async_client, admin["email"], admin["password"])
    assert payload["user"]["email"] == admin["email"]

    response = await async_client.get("/api/auth/session")
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == admin["email"]
    assert data["user"]["role"] == "admin"


async def test_provider_discovery_returns_config(async_client: AsyncClient, override_app_settings) -> None:
    """GET /auth/providers should expose configured SSO metadata."""

    override_app_settings(
        auth_force_sso=True,
        auth_providers=[
            {
                "id": "entra",
                "label": "Microsoft Entra ID",
                "start_url": "/auth/sso/login",
                "icon_url": "/static/entra.svg",
            },
            {
                "id": "okta",
                "label": "Okta",
                "start_url": "https://sso.example.test/start",
                "icon_url": None,
            },
        ],
    )

    response = await async_client.get("/api/auth/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["force_sso"] is True
    assert payload["providers"] == [
        {
            "id": "entra",
            "label": "Microsoft Entra ID",
            "start_url": "/auth/sso/login",
            "icon_url": "/static/entra.svg",
        },
        {
            "id": "okta",
            "label": "Okta",
            "start_url": "https://sso.example.test/start",
            "icon_url": None,
        },
    ]


async def test_provider_discovery_defaults(async_client: AsyncClient, override_app_settings) -> None:
    """Discovery should return an empty list when no providers are configured."""

    override_app_settings(auth_force_sso=False, auth_providers=[])

    response = await async_client.get("/api/auth/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"providers": [], "force_sso": False}

async def test_login_sets_csrf_cookie_and_header(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Login responses should surface CSRF metadata for the frontend."""

    admin = seed_identity["admin"]
    response = await async_client.post(
        "/api/auth/session",
        json={"email": admin["email"], "password": admin["password"]},
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("X-CSRF-Token")
    assert async_client.cookies.get(CSRF_COOKIE)

async def test_invalid_credentials_rejected(async_client: AsyncClient) -> None:
    """Submitting an unknown user should produce 401."""

    response = await async_client.post(
        "/api/auth/session",
        json={"email": "missing@example.test", "password": "nope"},
    )
    assert response.status_code == 401


async def test_repeated_failed_logins_lock_account(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Too many failed password attempts should lock the account."""

    user = seed_identity["user"]
    lock_threshold = get_settings().failed_login_lock_threshold
    for _ in range(lock_threshold):
        response = await async_client.post(
            "/api/auth/session",
            json={"email": user["email"], "password": "wrong-password"},
        )
        assert response.status_code == 401

    locked = await async_client.post(
        "/api/auth/session",
        json={"email": user["email"], "password": user["password"]},
    )
    assert locked.status_code == 403
    payload = locked.json()["detail"]
    assert isinstance(payload, dict)
    assert payload.get("failedAttempts") == lock_threshold
    assert isinstance(payload.get("lockedUntil"), str)
    assert "temporarily locked" in payload.get("message", "")
    assert isinstance(payload.get("retryAfterSeconds"), int)
    retry_after_header = locked.headers.get("Retry-After")
    assert retry_after_header is not None


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
        "/api/auth/session",
        json={"email": username, "password": password},
    )
    assert response.status_code == 422, response.text

    payload = response.json()
    assert isinstance(payload.get("detail"), list)
    messages = {error.get("msg", "") for error in payload["detail"]}
    for expected in expected_messages:
        assert any(expected in message for message in messages)

async def test_profile_requires_authentication(async_client: AsyncClient) -> None:
    """GET /auth/session should require a valid session."""

    response = await async_client.get("/api/auth/session")
    assert response.status_code == 401

async def test_refresh_requires_csrf_header(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """POST /auth/refresh should enforce the double submit cookie check."""

    admin = seed_identity["admin"]
    await _login(async_client, admin["email"], admin["password"])

    missing = await async_client.post("/api/auth/session/refresh")
    assert missing.status_code == 403

    rotated = await async_client.post(
        "/api/auth/session/refresh",
        headers=_csrf_headers(async_client),
    )
    assert rotated.status_code == 200, rotated.text
    payload = rotated.json()
    assert payload["user"]["email"] == admin["email"]

async def test_api_key_rotation_and_revocation(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Issued API keys should support rotation and revocation."""

    admin = seed_identity["admin"]
    await _login(async_client, admin["email"], admin["password"])

    first = await async_client.post(
        "/api/auth/api-keys",
        json={"email": admin["email"], "label": "Primary key"},
        headers=_csrf_headers(async_client),
    )
    assert first.status_code == 201, first.text
    first_payload = first.json()
    first_key = first_payload["api_key"]
    assert first_payload["label"] == "Primary key"
    first_prefix, _ = first_key.split(".", 1)

    second = await async_client.post(
        "/api/auth/api-keys",
        json={"email": admin["email"], "label": "Secondary key"},
        headers=_csrf_headers(async_client),
    )
    assert second.status_code == 201, second.text
    second_payload = second.json()
    second_key = second_payload["api_key"]
    assert second_payload["label"] == "Secondary key"
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
    assert first_record["label"] == "Primary key"
    assert first_record["revoked_at"] is None
    assert second_record["principal_type"] == "user"
    assert second_record["principal_label"] == admin["email"]
    assert second_record["label"] == "Secondary key"
    assert second_record["revoked_at"] is None

    async_client.cookies.clear()
    response = await async_client.get("/api/auth/session", headers={"X-API-Key": first_key})
    assert response.status_code == 200
    response = await async_client.get("/api/auth/session", headers={"X-API-Key": second_key})
    assert response.status_code == 200

    await _login(async_client, admin["email"], admin["password"])
    revoke = await async_client.delete(
        f"/api/auth/api-keys/{first_record['api_key_id']}",
        headers=_csrf_headers(async_client),
    )
    assert revoke.status_code == 204

    async_client.cookies.clear()
    denied = await async_client.get("/api/auth/session", headers={"X-API-Key": first_key})
    assert denied.status_code == 401
    allowed = await async_client.get("/api/auth/session", headers={"X-API-Key": second_key})
    assert allowed.status_code == 200

    await _login(async_client, admin["email"], admin["password"])
    remaining = await async_client.get("/api/auth/api-keys")
    payload = remaining.json()
    assert [record["token_prefix"] for record in payload] == [second_prefix]
    assert payload[0]["principal_type"] == "user"
    assert payload[0]["principal_label"] == admin["email"]
    assert payload[0]["label"] == "Secondary key"
    assert payload[0]["revoked_at"] is None


async def test_api_key_issue_marks_service_account(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Issuing a key for a service account should expose its type."""

    admin = seed_identity["admin"]
    await _login(async_client, admin["email"], admin["password"])

    session_factory = get_sessionmaker()
    service_email = f"svc-robot+{uuid4().hex[:8]}@example.test"

    async with session_factory() as session:
        repo = UsersRepository(session)
        service_account = await repo.create(
            email=service_email,
            password_hash=None,
            is_service_account=True,
        )
        await session.commit()

    response = await async_client.post(
        "/api/auth/api-keys",
        json={"user_id": service_account.id, "label": "Robot"},
        headers=_csrf_headers(async_client),
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["principal_type"] == "service_account"
    assert payload["principal_label"] == service_email
    assert payload["label"] == "Robot"

    listing = await async_client.get("/api/auth/api-keys")
    records = listing.json()
    target = next(
        record for record in records if record["principal_id"] == service_account.id
    )
    assert target["principal_type"] == "service_account"
    assert target["label"] == "Robot"
    assert target["revoked_at"] is None

    api_key = payload["api_key"]
    async_client.cookies.clear()
    authorised = await async_client.get("/api/auth/session", headers={"X-API-Key": api_key})
    assert authorised.status_code == 200
    body = authorised.json()
    assert body["user"]["email"] == service_email


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

async def test_logout_clears_cookies(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """POST /auth/logout should remove authentication cookies."""

    admin = seed_identity["admin"]
    await _login(async_client, admin["email"], admin["password"])

    forbidden = await async_client.request("DELETE", "/api/auth/session")
    assert forbidden.status_code == 403

    response = await async_client.request(
        "DELETE",
        "/api/auth/session",
        headers=_csrf_headers(async_client),
    )
    assert response.status_code == 204
    assert async_client.cookies.get("ade_session") is None
    assert async_client.cookies.get("ade_refresh") is None

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

