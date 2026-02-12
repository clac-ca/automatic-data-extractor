from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_api.features.admin_settings.service import DEFAULT_SAFE_MODE_DETAIL
from ade_api.features.sso.group_sync import GroupSyncStats
from ade_api.features.sso.oidc import OidcMetadata
from ade_api.features.sso.service import SsoService
from ade_api.settings import Settings
from ade_db.models import ApplicationSetting, SsoIdentity, SsoProviderStatus, User

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


def _set_runtime_auth_mode_password_and_idp(
    session: Session,
    *,
    provisioning_mode: str = "jit",
) -> None:
    payload = {
        "safe_mode": {
            "enabled": False,
            "detail": DEFAULT_SAFE_MODE_DETAIL,
        },
        "auth": {
            "mode": "password_and_idp",
            "password": {
                "reset_enabled": True,
                "mfa_required": False,
                "complexity": {
                    "min_length": 12,
                    "require_uppercase": False,
                    "require_lowercase": False,
                    "require_number": False,
                    "require_symbol": False,
                },
                "lockout": {
                    "max_attempts": 5,
                    "duration_seconds": 300,
                },
            },
            "identity_provider": {
                "provisioning_mode": provisioning_mode,
            },
        },
    }
    record = session.get(ApplicationSetting, 1)
    if record is None:
        session.add(
            ApplicationSetting(
                id=1,
                schema_version=2,
                data=payload,
                revision=1,
            )
        )
    else:
        record.schema_version = 2
        record.data = payload
        record.revision = int(record.revision) + 1
    session.commit()


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_runtime_auth_mode_password_and_idp(session)
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_runtime_auth_mode_password_and_idp(session)
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_runtime_auth_mode_password_and_idp(session)
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


@pytest.mark.parametrize("provisioning_mode", ["disabled", "scim"])
async def test_callback_sso_blocks_unknown_user_when_auto_provision_is_disabled(
    async_client: AsyncClient,
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    provisioning_mode: str,
) -> None:
    _set_runtime_auth_mode_password_and_idp(session, provisioning_mode=provisioning_mode)
    provider_id = _configure_provider(session, settings)
    state = _create_auth_state(session, settings, provider_id)

    _mock_oidc_callback(
        monkeypatch,
        claims={
            "sub": "legacy-subject-mode",
            "tid": "tenant-id",
            "oid": "object-id-mode",
            "email": "new.user@example.com",
        },
    )

    response = await async_client.get(
        f"/api/v1/auth/sso/callback?code=abc123&state={state}",
        headers={"accept": "application/json"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "AUTO_PROVISION_DISABLED"
    assert (
        session.execute(select(User).where(User.email_normalized == "new.user@example.com")).scalar_one_or_none()
        is None
    )


async def test_callback_sso_blocks_unverified_email_link_to_existing_user(
    async_client: AsyncClient,
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_runtime_auth_mode_password_and_idp(session)
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


async def test_callback_sso_hydrates_group_memberships_and_sets_external_id(
    async_client: AsyncClient,
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.auth_group_sync_tenant_id = "tenant-id"
    settings.auth_group_sync_client_id = "client-id"
    settings.auth_group_sync_client_secret = "client-secret"  # type: ignore[assignment]
    _set_runtime_auth_mode_password_and_idp(session)
    provider_id = _configure_provider(session, settings)
    state = _create_auth_state(session, settings, provider_id)

    _mock_oidc_callback(
        monkeypatch,
        claims={
            "sub": "legacy-subject-5",
            "tid": "tenant-id",
            "oid": "object-id-5",
            "email": "hydrated.user@example.com",
        },
    )

    captured: dict[str, str] = {}

    def _fake_sync_user_memberships(self, *, settings, user, user_external_id):  # noqa: ANN001
        del self
        del settings
        captured["user_id"] = str(user.id)
        captured["external_id"] = user_external_id
        return GroupSyncStats(
            known_users_linked=1,
            users_created=0,
            groups_upserted=1,
            memberships_added=1,
            memberships_removed=0,
            unknown_members_skipped=0,
        )

    monkeypatch.setattr(
        "ade_api.features.auth.sso_router.GroupSyncService.sync_user_memberships",
        _fake_sync_user_memberships,
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
        .where(SsoIdentity.subject == "tenant-id:object-id-5")
        .limit(1)
    ).scalar_one_or_none()
    assert identity is not None
    user = session.get(User, identity.user_id)
    assert user is not None
    assert user.source == "idp"
    assert user.external_id == "object-id-5"
    assert captured["user_id"] == str(user.id)
    assert captured["external_id"] == "object-id-5"


async def test_callback_sso_allows_login_when_membership_hydration_fails(
    async_client: AsyncClient,
    session: Session,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.auth_group_sync_tenant_id = "tenant-id"
    settings.auth_group_sync_client_id = "client-id"
    settings.auth_group_sync_client_secret = "client-secret"  # type: ignore[assignment]
    _set_runtime_auth_mode_password_and_idp(session)
    provider_id = _configure_provider(session, settings)
    state = _create_auth_state(session, settings, provider_id)

    _mock_oidc_callback(
        monkeypatch,
        claims={
            "sub": "legacy-subject-6",
            "tid": "tenant-id",
            "oid": "object-id-6",
            "email": "retry.user@example.com",
        },
    )

    def _raising_sync(self, *, settings, user, user_external_id):  # noqa: ANN001
        del self, settings, user, user_external_id
        raise RuntimeError("transient graph error")

    retry_calls: list[dict[str, str]] = []

    def _fake_retry(*, request, settings, user_id, user_external_id):  # noqa: ANN001
        del request, settings
        retry_calls.append({"user_id": str(user_id), "external_id": user_external_id})

    monkeypatch.setattr(
        "ade_api.features.auth.sso_router.GroupSyncService.sync_user_memberships",
        _raising_sync,
    )
    monkeypatch.setattr(
        "ade_api.features.auth.sso_router._hydrate_user_memberships_retry",
        _fake_retry,
    )

    response = await async_client.get(
        f"/api/v1/auth/sso/callback?code=abc123&state={state}",
        headers={"accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(retry_calls) == 1
    assert retry_calls[0]["external_id"] == "object-id-6"
