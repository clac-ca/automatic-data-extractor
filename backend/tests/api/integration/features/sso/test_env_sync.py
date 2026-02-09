from __future__ import annotations

import uuid

from ade_api.features.sso.env_sync import sync_sso_providers_from_env
from ade_api.features.sso.service import SsoService
from ade_db.models import SsoProvider, SsoProviderManagedBy, SsoProviderStatus
from ade_api.settings import Settings


def _provider_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _settings_with_env(raw: str | None) -> Settings:
    return Settings(
        _env_file=None,
        secret_key="test-secret-key-for-tests-please-change",
        sso_encryption_key="test-sso-encryption-key",
        auth_sso_providers_json=raw,
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_connection_string="UseDevelopmentStorage=true",
    )


def test_env_sync_creates_env_managed_provider(session) -> None:
    provider_id = _provider_id("okta-primary")
    raw = """
    [
      {
        "id": "__PROVIDER_ID__",
        "type": "oidc",
        "label": "Okta",
        "issuer": "https://issuer.example.com",
        "clientId": "client-1",
        "clientSecret": "secret-1",
        "domains": ["example.com"],
        "status": "active"
      }
    ]
    """
    settings = _settings_with_env(raw.replace("__PROVIDER_ID__", provider_id))

    sync_sso_providers_from_env(session=session, settings=settings)

    provider = session.get(SsoProvider, provider_id)
    assert provider is not None
    assert provider.managed_by == SsoProviderManagedBy.ENV
    assert provider.locked is True
    assert provider.label == "Okta"
    assert provider.status == SsoProviderStatus.ACTIVE
    assert sorted(domain.domain for domain in provider.domains) == ["example.com"]


def test_env_sync_updates_existing_provider(session, settings) -> None:
    provider_id = _provider_id("okta-update")
    service = SsoService(session=session, settings=settings)
    service.create_provider(
        provider_id=provider_id,
        label="Old",
        issuer="https://issuer.old.com",
        client_id="old-client",
        client_secret="notsecret-client-old",
        status_value=SsoProviderStatus.DISABLED,
        domains=["old.com"],
    )
    session.commit()

    raw = """
    [
      {
        "id": "__PROVIDER_ID__",
        "type": "oidc",
        "label": "New Label",
        "issuer": "https://issuer.example.com",
        "clientId": "new-client",
        "clientSecret": "new-secret",
        "domains": ["example.com"],
        "status": "active"
      }
    ]
    """
    env_settings = _settings_with_env(raw.replace("__PROVIDER_ID__", provider_id))

    sync_sso_providers_from_env(session=session, settings=env_settings)

    provider = session.get(SsoProvider, provider_id)
    assert provider is not None
    assert provider.managed_by == SsoProviderManagedBy.ENV
    assert provider.locked is True
    assert provider.label == "New Label"
    assert provider.status == SsoProviderStatus.ACTIVE
    assert sorted(domain.domain for domain in provider.domains) == ["example.com"]


def test_env_sync_releases_removed_env_provider(session, settings) -> None:
    provider_id = _provider_id("okta-release")
    service = SsoService(session=session, settings=settings)
    provider = service.create_provider(
        provider_id=provider_id,
        label="Okta",
        issuer="https://issuer.example.com",
        client_id="demo-client",
        client_secret="notsecret-client",
        status_value=SsoProviderStatus.DISABLED,
        domains=["example.com"],
    )
    provider.managed_by = SsoProviderManagedBy.ENV
    provider.locked = True
    session.commit()

    env_settings = _settings_with_env("[]")

    sync_sso_providers_from_env(session=session, settings=env_settings)

    refreshed = session.get(SsoProvider, provider_id)
    assert refreshed is not None
    assert refreshed.managed_by == SsoProviderManagedBy.DB
    assert refreshed.locked is False
