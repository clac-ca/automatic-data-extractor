from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
import sqlalchemy as sa
from fastapi import HTTPException

from ade_api.common.problem_details import ApiError
from ade_api.common.time import utc_now
from ade_api.features.sso.oidc import OidcDiscoveryError, OidcMetadata
from ade_api.features.sso.service import AUTH_STATE_TTL, AuthStateError, SsoService
from ade_db.models import (
    ApplicationSetting,
    SsoAuthState,
    SsoProvider,
    SsoProviderDomain,
    SsoProviderManagedBy,
    SsoProviderStatus,
)


def test_status_mapping_hides_deleted_state_in_ui() -> None:
    assert SsoService.db_status_to_ui_status(SsoProviderStatus.ACTIVE) == "active"
    assert SsoService.db_status_to_ui_status(SsoProviderStatus.DISABLED) == "disabled"
    assert SsoService.db_status_to_ui_status(SsoProviderStatus.DELETED) == "disabled"

    assert SsoService.ui_status_to_db_status("active") == SsoProviderStatus.ACTIVE
    assert SsoService.ui_status_to_db_status("disabled") == SsoProviderStatus.DISABLED


@pytest.fixture(autouse=True)
def _clear_sso_state(session) -> None:
    session.execute(sa.delete(SsoAuthState))
    session.execute(sa.delete(SsoProviderDomain))
    session.execute(sa.delete(SsoProvider))
    session.flush()


def _set_auth_policy(
    session,
    *,
    mode: str | None = None,
) -> None:
    record = session.get(ApplicationSetting, 1)
    assert record is not None

    data = dict(record.data)
    auth = dict(data.get("auth") or {})
    if mode is not None:
        auth["mode"] = str(mode)
    data["auth"] = auth
    record.data = data
    record.schema_version = 2
    record.revision = int(record.revision) + 1
    session.flush()


def test_create_provider_normalizes_domains(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    provider = service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=["Example.COM", " example.com ", "sub.example.com"],
    )

    domains = sorted(domain.domain for domain in provider.domains)
    assert domains == ["example.com", "sub.example.com"]


def test_create_provider_rejects_domain_conflict(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=["example.com"],
    )

    with pytest.raises(HTTPException) as excinfo:
        service.create_provider(
            provider_id="okta-secondary",
            label="Other",
            issuer="https://issuer.example.com",
            client_id="other-client",
            client_secret="notsecret-client-other",
            status_value=SsoProviderStatus.ACTIVE,
            domains=["example.com"],
        )

    assert excinfo.value.status_code == 409


def test_list_active_providers_respects_global_disable(session, settings) -> None:
    service = SsoService(session=session, settings=settings)
    _set_auth_policy(session, mode="password_and_idp")

    service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=[],
    )
    _set_auth_policy(session, mode="password_only")

    assert service.list_active_providers() == []


def test_resolve_provider_for_domain_matches_active_only(session, settings) -> None:
    service = SsoService(session=session, settings=settings)
    _set_auth_policy(session, mode="password_and_idp")

    active = service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=["Example.COM"],
    )
    service.create_provider(
        provider_id="okta-disabled",
        label="Okta Disabled",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.DISABLED,
        domains=["disabled.com"],
    )

    resolved = service.resolve_provider_for_domain("example.com")
    assert resolved is not None
    assert resolved.id == active.id
    assert service.resolve_provider_for_domain("disabled.com") is None


def test_consume_auth_state_marks_used_and_blocks_reuse(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=[],
    )
    service.create_auth_state(
        state="state-1",
        provider_id="okta-primary",
        nonce="nonce-123",
        pkce_verifier="verifier-123",
        return_to="/workspaces",
    )

    record = service.consume_auth_state(state="state-1", provider_id="okta-primary")
    assert record.consumed_at is not None

    with pytest.raises(AuthStateError) as excinfo:
        service.consume_auth_state(state="state-1", provider_id="okta-primary")

    assert excinfo.value.code == "STATE_REUSED"


def test_consume_auth_state_expired_raises(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=[],
    )

    now = utc_now()
    service.create_auth_state(
        state="state-expired",
        provider_id="okta-primary",
        nonce="nonce-123",
        pkce_verifier="verifier-123",
        return_to="/workspaces",
        now=now,
    )

    with pytest.raises(AuthStateError) as excinfo:
        service.consume_auth_state(
            state="state-expired",
            provider_id="okta-primary",
            now=now + AUTH_STATE_TTL + timedelta(seconds=1),
        )

    assert excinfo.value.code == "STATE_EXPIRED"


def test_update_provider_rejects_locked(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    provider = service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.DISABLED,
        domains=[],
    )
    provider.managed_by = SsoProviderManagedBy.ENV
    provider.locked = True
    session.flush()

    with pytest.raises(ApiError) as excinfo:
        service.update_provider(
            provider.id,
            label="New Label",
            issuer=None,
            client_id=None,
            client_secret=None,
            status_value=None,
            domains=None,
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.errors
    assert excinfo.value.errors[0].code == "sso_provider_locked"


def test_delete_provider_rejects_locked(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    provider = service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.DISABLED,
        domains=[],
    )
    provider.managed_by = SsoProviderManagedBy.ENV
    provider.locked = True
    session.flush()

    with pytest.raises(ApiError) as excinfo:
        service.delete_provider(provider.id)

    assert excinfo.value.status_code == 409
    assert excinfo.value.errors
    assert excinfo.value.errors[0].code == "sso_provider_locked"


def test_update_provider_rejects_disabling_last_active_provider_when_sso_enforced(
    session,
    settings,
) -> None:
    service = SsoService(session=session, settings=settings)
    _set_auth_policy(session, mode="idp_only")
    provider = service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=[],
    )

    with pytest.raises(ApiError) as excinfo:
        service.update_provider(
            provider.id,
            label=None,
            issuer=None,
            client_id=None,
            client_secret=None,
            status_value=SsoProviderStatus.DISABLED,
            domains=None,
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.errors
    assert excinfo.value.errors[0].code == "active_provider_required"


def test_delete_provider_rejects_last_active_provider_when_sso_enforced(
    session,
    settings,
) -> None:
    service = SsoService(session=session, settings=settings)
    _set_auth_policy(session, mode="idp_only")
    provider = service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=[],
    )

    with pytest.raises(ApiError) as excinfo:
        service.delete_provider(provider.id)

    assert excinfo.value.status_code == 422
    assert excinfo.value.errors
    assert excinfo.value.errors[0].code == "active_provider_required"


def test_delete_provider_allows_when_another_active_provider_exists_under_sso_enforcement(
    session,
    settings,
) -> None:
    service = SsoService(session=session, settings=settings)
    _set_auth_policy(session, mode="idp_only")
    first = service.create_provider(
        provider_id="okta-primary",
        label="Okta Primary",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=["example.com"],
    )
    service.create_provider(
        provider_id="okta-secondary",
        label="Okta Secondary",
        issuer="https://issuer2.example.com",
        client_id="demo-client-2",
        client_secret="notsecret-client-2",
        status_value=SsoProviderStatus.ACTIVE,
        domains=["example.org"],
    )

    service.delete_provider(first.id)
    assert first.status == SsoProviderStatus.DELETED


def test_update_provider_reactivates_deleted_provider(session, settings) -> None:
    service = SsoService(session=session, settings=settings)
    provider = service.create_provider(
        provider_id="okta-reactivate",
        label="Okta Reactivate",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.ACTIVE,
        domains=["reactivate.example.com"],
    )
    service.delete_provider(provider.id)
    assert provider.status == SsoProviderStatus.DELETED

    updated = service.update_provider(
        provider.id,
        label=None,
        issuer=None,
        client_id=None,
        client_secret=None,
        status_value=SsoProviderStatus.ACTIVE,
        domains=None,
    )
    assert updated.status == SsoProviderStatus.ACTIVE


def test_validate_provider_configuration_returns_discovery_metadata(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    metadata = service.validate_provider_configuration(
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
    )

    assert metadata.issuer == "https://issuer.example.com"
    assert metadata.authorization_endpoint.endswith("/oauth2/v1/authorize")
    assert metadata.token_endpoint.endswith("/oauth2/v1/token")
    assert metadata.jwks_uri.endswith("/oauth2/v1/keys")


def test_validate_provider_configuration_timeout_maps_problem_code(
    session,
    settings,
    monkeypatch,
) -> None:
    service = SsoService(session=session, settings=settings)

    def _raise_timeout(_issuer: str, _client) -> OidcMetadata:
        raise OidcDiscoveryError("Discovery request failed") from httpx.ReadTimeout(
            "timeout"
        )

    monkeypatch.setattr(
        "ade_api.features.sso.service.discover_metadata",
        _raise_timeout,
    )

    with pytest.raises(ApiError) as excinfo:
        service.validate_provider_configuration(
            issuer="https://issuer.example.com",
            client_id="demo-client",
            client_secret="notsecret-client",
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.errors
    assert excinfo.value.errors[0].code == "sso_validation_timeout"


def test_validate_provider_configuration_issuer_mismatch_maps_problem_code(
    session,
    settings,
    monkeypatch,
) -> None:
    service = SsoService(session=session, settings=settings)

    def _raise_issuer_mismatch(_issuer: str, _client) -> OidcMetadata:
        raise OidcDiscoveryError("Discovery issuer mismatch")

    monkeypatch.setattr(
        "ade_api.features.sso.service.discover_metadata",
        _raise_issuer_mismatch,
    )

    with pytest.raises(ApiError) as excinfo:
        service.validate_provider_configuration(
            issuer="https://issuer.example.com",
            client_id="demo-client",
            client_secret="notsecret-client",
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.errors
    assert excinfo.value.errors[0].code == "sso_issuer_mismatch"


def test_validate_provider_configuration_metadata_invalid_maps_problem_code(
    session,
    settings,
    monkeypatch,
) -> None:
    service = SsoService(session=session, settings=settings)

    def _raise_missing_endpoints(_issuer: str, _client) -> OidcMetadata:
        raise OidcDiscoveryError("Discovery response missing required endpoints")

    monkeypatch.setattr(
        "ade_api.features.sso.service.discover_metadata",
        _raise_missing_endpoints,
    )

    with pytest.raises(ApiError) as excinfo:
        service.validate_provider_configuration(
            issuer="https://issuer.example.com",
            client_id="demo-client",
            client_secret="notsecret-client",
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.errors
    assert excinfo.value.errors[0].code == "sso_metadata_invalid"


def test_create_active_provider_requires_successful_validation(
    session,
    settings,
    monkeypatch,
) -> None:
    service = SsoService(session=session, settings=settings)

    def _raise_discovery_failure(_issuer: str, _client) -> OidcMetadata:
        raise OidcDiscoveryError("Discovery response was not successful")

    monkeypatch.setattr(
        "ade_api.features.sso.service.discover_metadata",
        _raise_discovery_failure,
    )

    with pytest.raises(ApiError) as excinfo:
        service.create_provider(
            provider_id="okta-primary",
            label="Okta",
            issuer="https://issuer.example.com",
            client_id="demo-client",
            client_secret="notsecret-client",
            status_value=SsoProviderStatus.ACTIVE,
            domains=[],
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.errors
    assert excinfo.value.errors[0].code == "sso_discovery_failed"
