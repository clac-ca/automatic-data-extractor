"""Authentication endpoint tests."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from backend.api.modules.auth.service import SSO_STATE_COOKIE, AuthService, OIDCProviderMetadata
from backend.app import reload_settings


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


@pytest.mark.asyncio
async def test_api_key_rotation_and_revocation(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Issued API keys should support rotation and revocation."""

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])

    headers = {"Authorization": f"Bearer {token}"}
    first = await async_client.post(
        "/auth/api-keys",
        json={"email": admin["email"]},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    first_key = first.json()["api_key"]
    first_prefix, _ = first_key.split(".", 1)

    second = await async_client.post(
        "/auth/api-keys",
        json={"email": admin["email"]},
        headers=headers,
    )
    assert second.status_code == 201, second.text
    second_key = second.json()["api_key"]
    second_prefix, _ = second_key.split(".", 1)

    listing = await async_client.get("/auth/api-keys", headers=headers)
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

    response = await async_client.get("/auth/me", headers={"X-API-Key": first_key})
    assert response.status_code == 200
    response = await async_client.get("/auth/me", headers={"X-API-Key": second_key})
    assert response.status_code == 200

    revoke = await async_client.delete(
        f"/auth/api-keys/{first_record['api_key_id']}", headers=headers
    )
    assert revoke.status_code == 204

    denied = await async_client.get("/auth/me", headers={"X-API-Key": first_key})
    assert denied.status_code == 401
    allowed = await async_client.get("/auth/me", headers={"X-API-Key": second_key})
    assert allowed.status_code == 200

    remaining = await async_client.get("/auth/api-keys", headers=headers)
    payload = remaining.json()
    assert [record["token_prefix"] for record in payload] == [second_prefix]
    assert payload[0]["principal_type"] == "user"
    assert payload[0]["principal_label"] == admin["email"]


@pytest.mark.asyncio
async def test_service_account_api_keys(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Administrators should issue API keys to service accounts."""

    admin = seed_identity["admin"]
    service_account = seed_identity["service_account"]
    inactive_service_account = seed_identity["inactive_service_account"]
    token = await _login(async_client, admin["email"], admin["password"])

    headers = {"Authorization": f"Bearer {token}"}
    issued = await async_client.post(
        "/auth/api-keys",
        json={
            "user_id": service_account["id"],
        },
        headers=headers,
    )
    assert issued.status_code == 201, issued.text
    data = issued.json()
    assert data["principal_type"] == "service_account"
    assert data["principal_id"] == service_account["id"]
    assert data["principal_label"] == service_account["display_name"]
    api_key = data["api_key"]

    listing = await async_client.get("/auth/api-keys", headers=headers)
    assert listing.status_code == 200
    records = listing.json()
    lookup = {record["token_prefix"]: record for record in records}
    prefix, _ = api_key.split(".", 1)
    record = lookup[prefix]
    assert record["principal_type"] == "service_account"
    assert record["principal_id"] == service_account["id"]
    assert record["principal_label"] == service_account["display_name"]

    denied = await async_client.get("/auth/me", headers={"X-API-Key": api_key})
    assert denied.status_code == 403

    inactive = await async_client.post(
        "/auth/api-keys",
        json={
            "user_id": inactive_service_account["id"],
        },
        headers=headers,
    )
    assert inactive.status_code == 400


@pytest.mark.asyncio
async def test_service_account_password_login_blocked(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    """Password login should return 403 for service accounts."""

    service_account = seed_identity["service_account"]
    response = await async_client.post(
        "/auth/token",
        data={"username": service_account["email"], "password": "irrelevant"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sso_callback_rejects_state_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """The SSO callback should reject mismatched state tokens."""

    monkeypatch.setenv("ADE_SSO_CLIENT_ID", "demo-client")
    monkeypatch.setenv("ADE_SSO_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ADE_SSO_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("ADE_SSO_REDIRECT_URL", "https://ade.example.com/auth/sso/callback")
    monkeypatch.setenv("ADE_SSO_SCOPE", "openid email profile")
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

    login = await async_client.get("/auth/sso/login", follow_redirects=False)
    assert login.status_code in (302, 307)
    assert SSO_STATE_COOKIE in login.cookies
    state_cookie = login.cookies[SSO_STATE_COOKIE]

    callback = await async_client.get(
        "/auth/sso/callback",
        params={"code": "auth-code", "state": "wrong-state"},
        cookies={SSO_STATE_COOKIE: state_cookie},
    )
    assert callback.status_code == 400
