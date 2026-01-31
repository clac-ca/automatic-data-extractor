from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from ade_api.common.problem_details import ApiError
from ade_api.common.time import utc_now
from ade_api.features.sso.service import AUTH_STATE_TTL, AuthStateError, SsoService
from ade_api.models import SsoProviderManagedBy, SsoProviderStatus, SystemSetting


def test_create_provider_normalizes_domains(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    provider = service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="demo-secret",
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
        client_secret="demo-secret",
        status_value=SsoProviderStatus.ACTIVE,
        domains=["example.com"],
    )

    with pytest.raises(HTTPException) as excinfo:
        service.create_provider(
            provider_id="okta-secondary",
            label="Other",
            issuer="https://issuer.example.com",
            client_id="other-client",
            client_secret="other-secret",
            status_value=SsoProviderStatus.ACTIVE,
            domains=["example.com"],
        )

    assert excinfo.value.status_code == 409


def test_list_active_providers_respects_global_disable(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="demo-secret",
        status_value=SsoProviderStatus.ACTIVE,
        domains=[],
    )
    session.add(SystemSetting(key="sso-settings", value={"enabled": False}))
    session.flush()

    assert service.list_active_providers() == []


def test_resolve_provider_for_domain_matches_active_only(session, settings) -> None:
    service = SsoService(session=session, settings=settings)

    active = service.create_provider(
        provider_id="okta-primary",
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="demo-secret",
        status_value=SsoProviderStatus.ACTIVE,
        domains=["Example.COM"],
    )
    service.create_provider(
        provider_id="okta-disabled",
        label="Okta Disabled",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="demo-secret",
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
        client_secret="demo-secret",
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
        client_secret="demo-secret",
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
        client_secret="demo-secret",
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
        client_secret="demo-secret",
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
