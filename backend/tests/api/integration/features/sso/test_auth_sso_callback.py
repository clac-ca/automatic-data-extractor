from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_api.features.sso.oidc import OidcMetadata
from ade_api.features.sso.service import SsoService
from ade_api.settings import Settings
from ade_db.models import SsoIdentity, SsoProviderStatus, User

pytestmark = pytest.mark.asyncio

_ISSUER = "https://login.microsoftonline.com/test-tenant/v2.0"


def _configure_provider(session: Session, settings: Settings) -> str:
    service = SsoService(session=session, settings=settings)
    provider = service.create_provider(
        provider_id="entra",
        label="Microsoft Entra ID",
        issuer=_ISSUER,
        client_id="entra-client-id",
        client_secret="entra-client-secret",
        status_value=SsoProviderStatus.ACTIVE,
        domains=[],
    )
    session.commit()
    return provider.id


def _create_auth_state(session: Session, settings: Settings, provider_id: str) -> str:
    state = f"state-{uuid4().hex}"
    SsoService(session=session, settings=settings).create_auth_state(
        state=state,
        provider_id=provider_id,
        nonce="nonce-value",
        pkce_verifier="verifier-value",
        return_to="/",
    )
    session.commit()
    return state


def _mock_oidc_callback(monkeypatch: pytest.MonkeyPatch, *, claims: dict[str, object]) -> None:
    def _discover(_issuer: str, _client) -> OidcMetadata:
        return OidcMetadata(
            issuer=_ISSUER,
            authorization_endpoint=f"{_ISSUER}/authorize",
            token_endpoint=f"{_ISSUER}/token",
            jwks_uri=f"{_ISSUER}/keys",
        )

    def _exchange(**_kwargs):
        return {"id_token": "fake-id-token"}

    def _validate(**_kwargs):
        return claims

    monkeypatch.setattr("ade_api.features.auth.sso_router.discover_metadata", _discover)
    monkeypatch.setattr("ade_api.features.auth.sso_router.exchange_code", _exchange)
    monkeypatch.setattr("ade_api.features.auth.sso_router.validate_id_token", _validate)


async def test_callback_sso_allows_entra_login_without_email_verified_claim(
    async_client: AsyncClient,
    session: Session,
    settings: Settings,
    override_app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_app_settings(auth_mode="password_and_idp")
    provider_id = _configure_provider(session, settings)
    state = _create_auth_state(session, settings, provider_id)

    _mock_oidc_callback(
        monkeypatch,
        claims={
            "sub": "legacy-subject",
            "tid": "tenant-id",
            "oid": "object-id",
            "email": "entra.user@example.com",
        },
    )

    response = await async_client.get(
        f"/api/v1/auth/sso/callback?code=abc123&state={state}",
        headers={"accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True

    session.expire_all()
    identity = session.execute(
        select(SsoIdentity)
        .where(SsoIdentity.provider_id == provider_id)
        .where(SsoIdentity.subject == "tenant-id:object-id")
        .limit(1)
    ).scalar_one_or_none()
    assert identity is not None
    assert identity.email == "entra.user@example.com"
    assert identity.email_verified is False

    user = session.get(User, identity.user_id)
    assert user is not None
    assert user.email == "entra.user@example.com"


async def test_callback_sso_uses_preferred_username_when_email_claim_is_missing(
    async_client: AsyncClient,
    session: Session,
    settings: Settings,
    override_app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_app_settings(auth_mode="password_and_idp")
    provider_id = _configure_provider(session, settings)
    state = _create_auth_state(session, settings, provider_id)

    _mock_oidc_callback(
        monkeypatch,
        claims={
            "sub": "legacy-subject-2",
            "tid": "tenant-id",
            "oid": "object-id-2",
            "preferred_username": "preferred.user@example.com",
        },
    )

    response = await async_client.get(
        f"/api/v1/auth/sso/callback?code=abc123&state={state}",
        headers={"accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True

    session.expire_all()
    identity = session.execute(
        select(SsoIdentity)
        .where(SsoIdentity.provider_id == provider_id)
        .where(SsoIdentity.subject == "tenant-id:object-id-2")
        .limit(1)
    ).scalar_one_or_none()
    assert identity is not None
    assert identity.email == "preferred.user@example.com"


async def test_callback_sso_returns_email_missing_when_no_email_claim_candidates_exist(
    async_client: AsyncClient,
    session: Session,
    settings: Settings,
    override_app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_app_settings(auth_mode="password_and_idp")
    provider_id = _configure_provider(session, settings)
    state = _create_auth_state(session, settings, provider_id)

    _mock_oidc_callback(
        monkeypatch,
        claims={
            "sub": "legacy-subject-3",
            "tid": "tenant-id",
            "oid": "object-id-3",
        },
    )

    response = await async_client.get(
        f"/api/v1/auth/sso/callback?code=abc123&state={state}",
        headers={"accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "EMAIL_MISSING"


async def test_callback_sso_blocks_unverified_email_link_to_existing_user(
    async_client: AsyncClient,
    session: Session,
    settings: Settings,
    override_app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_app_settings(auth_mode="password_and_idp")
    provider_id = _configure_provider(session, settings)
    state = _create_auth_state(session, settings, provider_id)

    existing_user = User(
        email="existing.user@example.com",
        hashed_password="not-used-for-sso",
        display_name="Existing User",
        is_active=True,
        is_verified=True,
        is_service_account=False,
    )
    session.add(existing_user)
    session.commit()

    _mock_oidc_callback(
        monkeypatch,
        claims={
            "sub": "legacy-subject-4",
            "tid": "tenant-id",
            "oid": "object-id-4",
            "email": "existing.user@example.com",
        },
    )

    response = await async_client.get(
        f"/api/v1/auth/sso/callback?code=abc123&state={state}",
        headers={"accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "EMAIL_LINK_UNVERIFIED"
