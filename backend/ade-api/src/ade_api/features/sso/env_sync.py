"""Startup sync for env-managed SSO providers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Annotated

import sqlalchemy as sa
from pydantic import Field, SecretStr, ValidationError, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_api.common.logging import log_context
from ade_api.common.time import utc_now
from ade_api.core.security.secrets import encrypt_secret
from ade_api.features.sso.schemas import PROVIDER_ID_PATTERN, SsoProviderAdminBase
from ade_db.models import (
    SsoProvider,
    SsoProviderDomain,
    SsoProviderManagedBy,
    SsoProviderStatus,
)
from ade_api.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EnvProviderConfig:
    id: str
    label: str
    issuer: str
    client_id: str
    client_secret: str
    status: SsoProviderStatus
    domains: list[str]


class EnvSsoProvider(SsoProviderAdminBase):
    id: Annotated[str, Field(pattern=PROVIDER_ID_PATTERN)]
    client_secret: SecretStr = Field(..., alias="clientSecret")
    is_default: bool | None = Field(default=None, alias="isDefault")

    @field_validator("id")
    @classmethod
    def _clean_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Provider ID must not be blank")
        return cleaned

    @field_validator("client_secret")
    @classmethod
    def _clean_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Client secret must not be blank")
        return value

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: SsoProviderStatus) -> SsoProviderStatus:
        status_value = value.value if isinstance(value, SsoProviderStatus) else str(value)
        if status_value == SsoProviderStatus.DELETED.value:
            raise ValueError("status must be active or disabled")
        return value


def _normalize_domain(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned:
        raise ValueError("Domain must not be blank")
    if any(token in cleaned for token in ("@", "/", ":", "\\")):
        raise ValueError("Domain must not include protocol or user info")
    try:
        cleaned = cleaned.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Domain must be valid ASCII/IDNA") from exc
    return cleaned


def _normalize_domains(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        domain = _normalize_domain(value)
        if domain not in seen:
            seen.add(domain)
            normalized.append(domain)
    return normalized


def _parse_env_providers(raw: str) -> list[EnvProviderConfig]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ADE_AUTH_SSO_PROVIDERS_JSON must be valid JSON") from exc

    if not isinstance(payload, list):
        raise RuntimeError("ADE_AUTH_SSO_PROVIDERS_JSON must be a JSON array")

    configs: list[EnvProviderConfig] = []
    seen_ids: set[str] = set()
    seen_domains: set[str] = set()

    for entry in payload:
        try:
            parsed = EnvSsoProvider.model_validate(entry)
        except ValidationError as exc:
            raise RuntimeError("ADE_AUTH_SSO_PROVIDERS_JSON contains invalid provider data") from exc

        if parsed.id in seen_ids:
            raise RuntimeError(f"Duplicate provider id in ADE_AUTH_SSO_PROVIDERS_JSON: {parsed.id}")
        seen_ids.add(parsed.id)

        normalized_domains = _normalize_domains(parsed.domains)
        for domain in normalized_domains:
            if domain in seen_domains:
                raise RuntimeError(
                    f"Duplicate domain in ADE_AUTH_SSO_PROVIDERS_JSON: {domain}"
                )
            seen_domains.add(domain)

        configs.append(
            EnvProviderConfig(
                id=parsed.id,
                label=parsed.label,
                issuer=parsed.issuer,
                client_id=parsed.client_id,
                client_secret=parsed.client_secret.get_secret_value(),
                status=parsed.status,
                domains=normalized_domains,
            )
        )

    return configs


def sync_sso_providers_from_env(*, session: Session, settings: Settings) -> None:
    raw = settings.auth_sso_providers_json
    if raw is None:
        logger.debug("sso.env_sync.skipped", extra=log_context(reason="not_configured"))
        return

    providers = _parse_env_providers(raw)
    now = utc_now()

    for provider in providers:
        _upsert_provider(session, settings=settings, provider=provider, now=now)
        _sync_domains(session, provider_id=provider.id, domains=provider.domains, now=now)

    release_stmt = sa.update(SsoProvider).where(
        SsoProvider.managed_by == SsoProviderManagedBy.ENV
    )
    if providers:
        release_stmt = release_stmt.where(SsoProvider.id.not_in({p.id for p in providers}))
    release_stmt = release_stmt.values(
        managed_by=SsoProviderManagedBy.DB,
        locked=False,
        updated_at=now,
    )
    released = session.execute(release_stmt)

    logger.info(
        "sso.env_sync.complete",
        extra=log_context(env_count=len(providers), released=int(released.rowcount or 0)),
    )


def _upsert_provider(
    session: Session,
    *,
    settings: Settings,
    provider: EnvProviderConfig,
    now,
) -> None:
    secret_enc = encrypt_secret(provider.client_secret, settings)
    insert_values = {
        "id": provider.id,
        "type": "oidc",
        "label": provider.label,
        "issuer": provider.issuer,
        "client_id": provider.client_id,
        "client_secret_enc": secret_enc,
        "status": provider.status,
        "managed_by": SsoProviderManagedBy.ENV,
        "locked": True,
        "created_at": now,
        "updated_at": now,
    }
    update_values = {
        "type": "oidc",
        "label": provider.label,
        "issuer": provider.issuer,
        "client_id": provider.client_id,
        "client_secret_enc": secret_enc,
        "status": provider.status,
        "managed_by": SsoProviderManagedBy.ENV,
        "locked": True,
        "updated_at": now,
    }

    for attempt in range(2):
        try:
            with session.begin_nested():
                update_stmt = (
                    sa.update(SsoProvider)
                    .where(SsoProvider.id == provider.id)
                    .values(**update_values)
                )
                result = session.execute(update_stmt)
                if result.rowcount:
                    return
                session.execute(sa.insert(SsoProvider).values(**insert_values))
            return
        except IntegrityError:
            if attempt == 0:
                continue
            raise


def _sync_domains(
    session: Session,
    *,
    provider_id: str,
    domains: list[str],
    now,
) -> None:
    if domains:
        session.execute(
            sa.delete(SsoProviderDomain)
            .where(SsoProviderDomain.provider_id == provider_id)
            .where(SsoProviderDomain.domain.not_in(domains))
        )
    else:
        session.execute(
            sa.delete(SsoProviderDomain).where(SsoProviderDomain.provider_id == provider_id)
        )

    for domain in domains:
        for attempt in range(2):
            try:
                with session.begin_nested():
                    update_stmt = (
                        sa.update(SsoProviderDomain)
                        .where(SsoProviderDomain.domain == domain)
                        .values(provider_id=provider_id)
                    )
                    result = session.execute(update_stmt)
                    if result.rowcount:
                        break
                    session.execute(
                        sa.insert(SsoProviderDomain).values(
                            provider_id=provider_id,
                            domain=domain,
                            created_at=now,
                        )
                    )
                break
            except IntegrityError:
                existing = session.execute(
                    sa.select(SsoProviderDomain).where(SsoProviderDomain.domain == domain)
                ).scalar_one_or_none()
                if existing is not None and existing.provider_id == provider_id:
                    break
                if attempt == 0:
                    continue
                raise


__all__ = ["sync_sso_providers_from_env"]
