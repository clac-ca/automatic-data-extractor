"""Service layer for SSO provider configuration and auth state."""

from __future__ import annotations

import enum
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, NoReturn

import httpx
import sqlalchemy as sa
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ade_api.common.logging import log_context
from ade_api.common.problem_details import (
    ApiError,
    ProblemDetailsErrorItem,
    resolve_error_definition,
)
from ade_api.common.time import utc_now
from ade_api.core.security.secrets import decrypt_secret, encrypt_secret
from ade_api.features.admin_settings.service import RuntimeSettingsService
from ade_api.features.sso.oidc import OidcDiscoveryError, OidcMetadata, discover_metadata
from ade_api.settings import Settings
from ade_db.models import (
    SsoAuthState,
    SsoProvider,
    SsoProviderDomain,
    SsoProviderStatus,
)

logger = logging.getLogger(__name__)

AUTH_STATE_TTL = timedelta(minutes=10)


class AuthStateError(RuntimeError):
    """Raised when auth-state validation fails."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_LOCKED_PROVIDER_MESSAGE = "Provider is locked because it is managed by environment configuration."


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


def _normalize_domains(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        domain = _normalize_domain(value)
        if domain not in seen:
            seen.add(domain)
            normalized.append(domain)
    return normalized


def _enum_value(raw: object) -> str:
    if isinstance(raw, enum.Enum):
        return str(raw.value)
    return str(raw)


@dataclass(slots=True)
class SsoService:
    """CRUD helpers for SSO providers and auth state records."""

    session: Session
    settings: Settings

    # -- Providers -----------------------------------------------------

    def list_providers(self) -> list[SsoProvider]:
        stmt = sa.select(SsoProvider).order_by(SsoProvider.id.asc())
        return list(self.session.execute(stmt).scalars())

    @staticmethod
    def db_status_to_ui_status(
        status_value: SsoProviderStatus,
    ) -> Literal["active", "disabled"]:
        if status_value == SsoProviderStatus.ACTIVE:
            return "active"
        return "disabled"

    @staticmethod
    def ui_status_to_db_status(
        status_value: Literal["active", "disabled"],
    ) -> SsoProviderStatus:
        if status_value == "active":
            return SsoProviderStatus.ACTIVE
        return SsoProviderStatus.DISABLED

    def get_provider(self, provider_id: str) -> SsoProvider:
        provider = self.session.get(SsoProvider, provider_id)
        if provider is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Provider not found")
        return provider

    def create_provider(
        self,
        *,
        provider_id: str,
        label: str,
        issuer: str,
        client_id: str,
        client_secret: str,
        status_value: SsoProviderStatus,
        domains: Iterable[str],
    ) -> SsoProvider:
        if status_value == SsoProviderStatus.ACTIVE:
            self.validate_provider_configuration(
                issuer=issuer,
                client_id=client_id,
                client_secret=client_secret,
            )

        secret_enc = encrypt_secret(client_secret, self.settings)
        provider = SsoProvider(
            id=provider_id,
            label=label,
            issuer=issuer,
            client_id=client_id,
            client_secret_enc=secret_enc,
            status=status_value,
        )
        self.session.add(provider)

        normalized_domains = _normalize_domains(domains)
        self._apply_domains(provider, normalized_domains)

        self._ensure_active_provider_is_configured(provider)

        try:
            self.session.flush()
        except IntegrityError as exc:
            logger.warning(
                "sso.providers.create.integrity_conflict",
                extra=log_context(provider_id=provider_id),
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Provider already exists or domain conflict",
            ) from exc

        logger.info(
            "sso.providers.create.success",
            extra=log_context(provider_id=provider_id, status=_enum_value(provider.status)),
        )
        return provider

    def update_provider(
        self,
        provider_id: str,
        *,
        label: str | None,
        issuer: str | None,
        client_id: str | None,
        client_secret: str | None,
        status_value: SsoProviderStatus | None,
        domains: Iterable[str] | None,
    ) -> SsoProvider:
        provider = self.get_provider(provider_id)
        self._ensure_provider_mutable(provider)
        target_status = status_value or provider.status
        self._ensure_provider_status_change_allowed(
            provider=provider,
            target_status=target_status,
        )

        should_validate_active_provider = target_status == SsoProviderStatus.ACTIVE and (
            provider.status != SsoProviderStatus.ACTIVE
            or issuer is not None
            or client_id is not None
            or client_secret is not None
        )

        if should_validate_active_provider:
            self.validate_provider_configuration(
                issuer=issuer or provider.issuer,
                client_id=client_id or provider.client_id,
                client_secret=(
                    client_secret
                    if client_secret is not None
                    else decrypt_secret(provider.client_secret_enc, self.settings)
                ),
            )

        if label is not None:
            provider.label = label
        if issuer is not None:
            provider.issuer = issuer
        if client_id is not None:
            provider.client_id = client_id
        if client_secret is not None:
            provider.client_secret_enc = encrypt_secret(client_secret, self.settings)
        if status_value is not None:
            provider.status = status_value

        if domains is not None:
            normalized_domains = _normalize_domains(domains)
            self._apply_domains(provider, normalized_domains)

        self._ensure_active_provider_is_configured(provider)

        try:
            self.session.flush()
        except IntegrityError as exc:
            logger.warning(
                "sso.providers.update.integrity_conflict",
                extra=log_context(provider_id=provider_id),
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Domain conflict detected",
            ) from exc

        logger.info(
            "sso.providers.update.success",
            extra=log_context(provider_id=provider_id, status=_enum_value(provider.status)),
        )
        return provider

    def validate_provider_configuration(
        self,
        *,
        issuer: str,
        client_id: str,
        client_secret: str,
    ) -> OidcMetadata:
        del client_id, client_secret
        try:
            with httpx.Client(follow_redirects=True) as client:
                return discover_metadata(issuer, client)
        except OidcDiscoveryError as exc:
            self._raise_validation_error(exc)

    def delete_provider(self, provider_id: str) -> None:
        provider = self.get_provider(provider_id)
        self._ensure_provider_mutable(provider)
        self._ensure_provider_status_change_allowed(
            provider=provider,
            target_status=SsoProviderStatus.DELETED,
        )
        provider.status = SsoProviderStatus.DELETED
        self.session.flush()
        logger.info(
            "sso.providers.delete.success",
            extra=log_context(provider_id=provider_id),
        )

    def list_active_providers(self) -> list[SsoProvider]:
        if not self.is_sso_enabled():
            return []
        stmt = (
            sa
            .select(SsoProvider)
            .where(SsoProvider.status == SsoProviderStatus.ACTIVE)
            .order_by(SsoProvider.id.asc())
        )
        return list(self.session.execute(stmt).scalars())

    def resolve_provider_for_domain(self, domain: str) -> SsoProvider | None:
        if not self.is_sso_enabled():
            return None
        normalized = _normalize_domain(domain)
        stmt = (
            sa
            .select(SsoProvider)
            .join(SsoProviderDomain, SsoProviderDomain.provider_id == SsoProvider.id)
            .where(SsoProviderDomain.domain == normalized)
            .where(SsoProvider.status == SsoProviderStatus.ACTIVE)
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def is_sso_enabled(self) -> bool:
        runtime = RuntimeSettingsService(
            session=self.session,
        ).get_effective_values()
        return runtime.auth.mode in {"idp_only", "password_and_idp"}

    # -- Auth state -----------------------------------------------------

    def create_auth_state(
        self,
        *,
        state: str,
        provider_id: str,
        nonce: str,
        pkce_verifier: str,
        return_to: str,
        now: datetime | None = None,
    ) -> SsoAuthState:
        timestamp = now or utc_now()
        self.purge_expired_auth_states(now=timestamp)
        record = SsoAuthState(
            state=state,
            provider_id=provider_id,
            nonce=nonce,
            pkce_verifier=pkce_verifier,
            return_to=return_to,
            created_at=timestamp,
            expires_at=timestamp + AUTH_STATE_TTL,
            consumed_at=None,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def consume_auth_state(
        self,
        *,
        state: str,
        provider_id: str,
        now: datetime | None = None,
    ) -> SsoAuthState:
        timestamp = now or utc_now()
        record = self.session.get(SsoAuthState, state)
        if record is None:
            raise AuthStateError("STATE_INVALID")
        if record.provider_id != provider_id:
            raise AuthStateError("STATE_INVALID")
        if record.expires_at < timestamp:
            raise AuthStateError("STATE_EXPIRED")
        if record.consumed_at is not None:
            raise AuthStateError("STATE_REUSED")

        update_stmt = (
            sa
            .update(SsoAuthState)
            .where(SsoAuthState.state == state)
            .where(SsoAuthState.consumed_at.is_(None))
            .where(SsoAuthState.expires_at >= timestamp)
            .values(consumed_at=timestamp)
        )
        result = self.session.execute(update_stmt)
        if int(getattr(result, "rowcount", 0) or 0) == 0:
            refreshed = self.session.get(SsoAuthState, state)
            if refreshed is None:
                raise AuthStateError("STATE_INVALID")
            if refreshed.expires_at < timestamp:
                raise AuthStateError("STATE_EXPIRED")
            raise AuthStateError("STATE_REUSED")

        record.consumed_at = timestamp
        return record

    def purge_expired_auth_states(self, *, now: datetime | None = None) -> int:
        timestamp = now or utc_now()
        stmt = sa.delete(SsoAuthState).where(SsoAuthState.expires_at < timestamp)
        result = self.session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    # -- Helpers --------------------------------------------------------

    def _apply_domains(self, provider: SsoProvider, domains: list[str]) -> None:
        if domains:
            conflict_stmt = (
                sa
                .select(SsoProviderDomain)
                .where(SsoProviderDomain.domain.in_(domains))
                .where(SsoProviderDomain.provider_id != provider.id)
                .limit(1)
            )
            conflict = self.session.execute(conflict_stmt).scalar_one_or_none()
            if conflict is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Domain already assigned to another provider",
                )

        existing = {domain.domain: domain for domain in provider.domains}
        desired = set(domains)

        for domain, record in list(existing.items()):
            if domain not in desired:
                self.session.delete(record)

        for domain in domains:
            if domain in existing:
                continue
            self.session.add(SsoProviderDomain(provider_id=provider.id, domain=domain))

    def _ensure_active_provider_is_configured(self, provider: SsoProvider) -> None:
        if provider.status != SsoProviderStatus.ACTIVE:
            return
        if not provider.issuer or not provider.client_id or not provider.client_secret_enc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provider must be fully configured to activate",
            )

    def _ensure_provider_status_change_allowed(
        self,
        *,
        provider: SsoProvider,
        target_status: SsoProviderStatus,
    ) -> None:
        if provider.status != SsoProviderStatus.ACTIVE:
            return
        if target_status == SsoProviderStatus.ACTIVE:
            return

        runtime = RuntimeSettingsService(session=self.session).get_effective_values()
        if runtime.auth.mode != "idp_only":
            return

        remaining_active = self.session.execute(
            sa
            .select(sa.func.count())
            .select_from(SsoProvider)
            .where(SsoProvider.status == SsoProviderStatus.ACTIVE)
            .where(SsoProvider.id != provider.id)
        ).scalar_one()
        if int(remaining_active) > 0:
            return

        raise ApiError(
            error_type="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Cannot disable the last active provider while "
                "identity provider-only sign-in is enabled."
            ),
            errors=[
                ProblemDetailsErrorItem(
                    path="status",
                    message=(
                        "At least one active provider is required while auth.mode is idp_only."
                    ),
                    code="active_provider_required",
                )
            ],
        )

    def _ensure_provider_mutable(self, provider: SsoProvider) -> None:
        if not provider.locked:
            return
        definition = resolve_error_definition(status.HTTP_409_CONFLICT)
        raise ApiError(
            error_type=definition.type,
            status_code=definition.status,
            detail=_LOCKED_PROVIDER_MESSAGE,
            errors=[
                ProblemDetailsErrorItem(
                    message=_LOCKED_PROVIDER_MESSAGE,
                    code="sso_provider_locked",
                )
            ],
        )

    def _raise_validation_error(self, exc: OidcDiscoveryError) -> NoReturn:
        cause = exc.__cause__
        detail = str(exc)
        normalized = detail.lower()

        if isinstance(cause, httpx.TimeoutException):
            code = "sso_validation_timeout"
            message = "Issuer discovery timed out. Verify network access and try again."
        elif "issuer mismatch" in normalized:
            code = "sso_issuer_mismatch"
            message = "Issuer validation failed because discovery metadata issuer did not match."
        elif "missing required endpoints" in normalized or "not json" in normalized:
            code = "sso_metadata_invalid"
            message = "Issuer discovery metadata is invalid or incomplete."
        else:
            code = "sso_discovery_failed"
            message = "Unable to discover OIDC metadata for the issuer."

        raise ApiError(
            error_type="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=message,
            errors=[
                ProblemDetailsErrorItem(
                    path="issuer",
                    message=message,
                    code=code,
                )
            ],
        ) from exc

    def decrypt_client_secret(self, provider: SsoProvider) -> str:
        return decrypt_secret(provider.client_secret_enc, self.settings)


__all__ = [
    "AUTH_STATE_TTL",
    "AuthStateError",
    "SsoService",
]
