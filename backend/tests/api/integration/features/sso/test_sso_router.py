from __future__ import annotations

import httpx
import pytest
import uuid
from httpx import AsyncClient

from ade_api.features.sso.oidc import OidcDiscoveryError
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


def _error_codes(payload: dict[str, object]) -> set[str]:
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return set()
    return {
        item.get("code")
        for item in errors
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    }


def _unique_token(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _admin_headers(async_client: AsyncClient, seeded_identity) -> dict[str, str]:
    token, _ = await login(
        async_client,
        email=seeded_identity.admin.email,
        password=seeded_identity.admin.password,
    )
    return {"X-API-Key": token}


async def test_validate_provider_returns_metadata(
    async_client: AsyncClient,
    seeded_identity,
) -> None:
    headers = await _admin_headers(async_client, seeded_identity)

    response = await async_client.post(
        "/api/v1/admin/sso/providers/validate",
        headers=headers,
        json={
            "issuer": "https://issuer.example.com",
            "clientId": "demo-client",
            "clientSecret": "notsecret-client",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {
        "issuer": "https://issuer.example.com",
        "authorizationEndpoint": "https://issuer.example.com/oauth2/v1/authorize",
        "tokenEndpoint": "https://issuer.example.com/oauth2/v1/token",
        "jwksUri": "https://issuer.example.com/oauth2/v1/keys",
    }


async def test_validate_provider_timeout_maps_problem_code(
    async_client: AsyncClient,
    seeded_identity,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_timeout(_issuer: str, _client):
        raise OidcDiscoveryError("Discovery request failed") from httpx.ReadTimeout(
            "timeout"
        )

    monkeypatch.setattr(
        "ade_api.features.sso.service.discover_metadata",
        _raise_timeout,
    )
    headers = await _admin_headers(async_client, seeded_identity)

    response = await async_client.post(
        "/api/v1/admin/sso/providers/validate",
        headers=headers,
        json={
            "issuer": "https://issuer.example.com",
            "clientId": "demo-client",
            "clientSecret": "notsecret-client",
        },
    )

    assert response.status_code == 422, response.text
    assert "sso_validation_timeout" in _error_codes(response.json())


async def test_create_active_provider_rejects_discovery_failure(
    async_client: AsyncClient,
    seeded_identity,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_discovery_failure(_issuer: str, _client):
        raise OidcDiscoveryError("Discovery response was not successful")

    monkeypatch.setattr(
        "ade_api.features.sso.service.discover_metadata",
        _raise_discovery_failure,
    )
    headers = await _admin_headers(async_client, seeded_identity)
    provider_id = _unique_token("okta-fail")

    response = await async_client.post(
        "/api/v1/admin/sso/providers",
        headers=headers,
        json={
            "id": provider_id,
            "label": "Okta",
            "issuer": "https://issuer.example.com",
            "clientId": "demo-client",
            "clientSecret": "notsecret-client",
            "status": "active",
            "domains": [f"{provider_id}.example.com"],
        },
    )

    assert response.status_code == 422, response.text
    assert "sso_discovery_failed" in _error_codes(response.json())


async def test_activate_provider_rejects_metadata_issuer_mismatch(
    async_client: AsyncClient,
    seeded_identity,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await _admin_headers(async_client, seeded_identity)
    provider_id = _unique_token("okta-mismatch")

    created = await async_client.post(
        "/api/v1/admin/sso/providers",
        headers=headers,
        json={
            "id": provider_id,
            "label": "Okta",
            "issuer": "https://issuer.example.com",
            "clientId": "demo-client",
            "clientSecret": "notsecret-client",
            "status": "disabled",
            "domains": [f"{provider_id}.example.com"],
        },
    )
    assert created.status_code == 201, created.text

    def _raise_mismatch(_issuer: str, _client):
        raise OidcDiscoveryError("Discovery issuer mismatch")

    monkeypatch.setattr(
        "ade_api.features.sso.service.discover_metadata",
        _raise_mismatch,
    )

    response = await async_client.patch(
        f"/api/v1/admin/sso/providers/{provider_id}",
        headers=headers,
        json={
            "status": "active",
            "clientSecret": "notsecret-client",
        },
    )

    assert response.status_code == 422, response.text
    assert "sso_issuer_mismatch" in _error_codes(response.json())


async def test_list_providers_never_exposes_deleted_status(
    async_client: AsyncClient,
    seeded_identity,
) -> None:
    headers = await _admin_headers(async_client, seeded_identity)
    provider_id = _unique_token("okta-ui-status")

    created = await async_client.post(
        "/api/v1/admin/sso/providers",
        headers=headers,
        json={
            "id": provider_id,
            "label": "Okta UI Status",
            "issuer": "https://issuer.example.com",
            "clientId": "demo-client",
            "clientSecret": "notsecret-client",
            "status": "disabled",
            "domains": [],
        },
    )
    assert created.status_code == 201, created.text

    deleted = await async_client.delete(
        f"/api/v1/admin/sso/providers/{provider_id}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    listed = await async_client.get(
        "/api/v1/admin/sso/providers",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    items = payload.get("items", [])
    assert isinstance(items, list)
    target = next(item for item in items if item.get("id") == provider_id)
    assert target["status"] == "disabled"
    assert all(item.get("status") in {"active", "disabled"} for item in items)
