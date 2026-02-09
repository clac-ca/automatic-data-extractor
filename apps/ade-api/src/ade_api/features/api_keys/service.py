"""Domain service for API key lifecycle and authentication."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ade_api.common.cursor_listing import ResolvedCursorSort, paginate_query_cursor
from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.time import utc_now
from ade_api.core.auth.errors import AuthenticationError
from ade_api.core.auth.principal import AuthenticatedPrincipal, AuthVia, PrincipalType
from ade_api.core.security.api_keys import (
    generate_api_key_prefix,
    generate_api_key_secret,
    hash_api_key_secret,
)
from ade_api.models import ApiKey, User
from ade_api.settings import Settings

from .filters import apply_api_key_filters


@dataclass(slots=True)
class ApiKeyCreateResult:
    """Result returned when a new API key is created."""

    api_key: ApiKey
    secret: str  # full secret, e.g. "prefix.secret"


@dataclass(slots=True)
class ApiKeyAuthenticationResult:
    """Result of authenticating a raw API key."""

    api_key: ApiKey
    user_id: UUID


class ApiKeyNotFoundError(LookupError):
    """Raised when an API key cannot be located."""


class ApiKeyAccessDeniedError(PermissionError):
    """Raised when a caller attempts to operate on a key they do not own."""


class ApiKeyRevokedError(PermissionError):
    """Raised when an API key is revoked but still used."""


class ApiKeyExpiredError(PermissionError):
    """Raised when an API key is expired but still used."""


class ApiKeyOwnerInactiveError(PermissionError):
    """Raised when the owner of an API key is inactive."""


class InvalidApiKeyFormatError(ValueError):
    """Raised when a raw API key token is malformed."""


def _normalize_label(label: str | None) -> str | None:
    if label is None:
        return None
    cleaned = label.strip()
    if not cleaned:
        return None
    return cleaned[:100]


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class ApiKeyService:
    """API key lifecycle & authentication."""

    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def create_for_user(
        self,
        *,
        user_id: UUID,
        name: str | None,
        expires_in_days: int | None,
    ) -> ApiKeyCreateResult:
        """Create a new API key for the specified owner."""

        owner = self._get_user(user_id=user_id)
        return self._create_api_key(
            user_id=owner.id,
            name=name,
            expires_in_days=expires_in_days,
        )

    def _get_user(self, *, user_id: UUID) -> User:
        owner = self._session.get(User, user_id)
        if owner is None:
            raise ValueError("Owner user not found")
        if not owner.is_active:
            raise ValueError("Owner user is inactive")
        return owner

    def _create_api_key(
        self,
        *,
        user_id: UUID,
        name: str | None,
        expires_in_days: int | None,
    ) -> ApiKeyCreateResult:
        name = _normalize_label(name)

        expires_at: datetime | None = None
        if expires_in_days is not None:
            expires_at = utc_now() + timedelta(days=expires_in_days)

        prefix_length = getattr(self._settings, "api_key_prefix_length", 12)
        secret_bytes = getattr(self._settings, "api_key_secret_bytes", 32)
        prefix = generate_api_key_prefix(prefix_length)
        secret_part = generate_api_key_secret(secret_bytes)
        token_hash = hash_api_key_secret(secret_part)

        api_key = ApiKey(
            user_id=user_id,
            name=name,
            prefix=prefix,
            hashed_secret=token_hash,
            expires_at=expires_at,
            revoked_at=None,
        )
        self._session.add(api_key)
        self._session.flush()
        self._session.refresh(api_key)

        secret = f"{prefix}.{secret_part}"
        return ApiKeyCreateResult(api_key=api_key, secret=secret)

    # -- Listing ----------------------------------------------------------

    def _base_query(self) -> Select[tuple[ApiKey]]:
        return select(ApiKey)

    def list_for_user(
        self,
        *,
        user_id: UUID,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        resolved_sort: ResolvedCursorSort[ApiKey],
        limit: int,
        cursor: str | None,
        include_total: bool,
    ):
        """List keys for a specific user (self-service and admin use)."""

        stmt = (
            self._base_query()
            .where(ApiKey.user_id == user_id)
        )
        stmt = apply_api_key_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )

        return paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )

    def list_all(
        self,
        *,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        resolved_sort: ResolvedCursorSort[ApiKey],
        user_id: UUID | None,
        limit: int,
        cursor: str | None,
        include_total: bool,
    ):
        """List keys across the tenant (admin use)."""

        stmt = self._base_query()
        if user_id is not None:
            stmt = stmt.where(ApiKey.user_id == user_id)
        stmt = apply_api_key_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )

        return paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )

    # -- Read / revoke ----------------------------------------------------

    def get_by_id(self, api_key_id: UUID) -> ApiKey:
        result = self._session.execute(self._base_query().where(ApiKey.id == api_key_id))
        api_key = result.scalar_one_or_none()
        if api_key is None:
            raise ApiKeyNotFoundError(f"API key {api_key_id} not found")
        return api_key

    def revoke(self, api_key_id: UUID) -> ApiKey:
        api_key = self.get_by_id(api_key_id)
        if api_key.revoked_at is not None:
            return api_key
        api_key.revoked_at = utc_now()
        self._session.flush()
        self._session.refresh(api_key)
        return api_key

    def revoke_for_user(
        self,
        *,
        api_key_id: UUID,
        user_id: UUID,
    ) -> ApiKey:
        """Revoke a key ensuring it belongs to a specific user."""

        api_key = self.get_by_id(api_key_id)
        if api_key.user_id != user_id:
            raise ApiKeyAccessDeniedError(
                f"API key {api_key_id} is not owned by user {user_id}"
            )
        if api_key.revoked_at is not None:
            return api_key
        api_key.revoked_at = utc_now()
        self._session.flush()
        self._session.refresh(api_key)
        return api_key

    def revoke_all_for_user(self, *, user_id: UUID) -> None:
        """Revoke all API keys owned by the specified user."""

        now = utc_now()
        self._session.execute(
            sa.update(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        self._session.flush()

    # -- Authentication ---------------------------------------------------

    def authenticate_token(
        self,
        raw_token: str,
        *,
        touch_usage: bool = True,
    ) -> ApiKeyAuthenticationResult:
        """Authenticate a raw API key token."""

        if "." not in raw_token:
            raise InvalidApiKeyFormatError("API key must contain a prefix separator '.'")

        prefix, secret = raw_token.split(".", 1)
        prefix = prefix.strip()
        secret = secret.strip()
        if not prefix or not secret:
            raise InvalidApiKeyFormatError("API key prefix and secret must be non-empty")

        result = self._session.execute(
            self._base_query()
            .where(ApiKey.prefix == prefix)
            .execution_options(populate_existing=True)
        )
        api_key = result.scalar_one_or_none()
        if api_key is None:
            raise ApiKeyNotFoundError("API key not recognized")

        now = utc_now()
        expires_at = _normalize_dt(api_key.expires_at)
        if expires_at is not None and expires_at < now:
            raise ApiKeyExpiredError("API key has expired")
        revoked_at = _normalize_dt(api_key.revoked_at)
        if revoked_at is not None and revoked_at <= now:
            raise ApiKeyRevokedError("API key has been revoked")

        expected_hash = api_key.hashed_secret
        candidate_hash = hash_api_key_secret(secret)
        if not secrets.compare_digest(expected_hash, candidate_hash):
            raise ApiKeyNotFoundError("API key not recognized")

        user = getattr(api_key, "user", None)
        if user is None:
            user = self._session.get(User, api_key.user_id)
        if user is None:
            raise ApiKeyNotFoundError("API key not recognized")
        if not user.is_active:
            raise ApiKeyOwnerInactiveError("API key owner is inactive")

        if touch_usage:
            api_key.last_used_at = now
            self._session.flush()

        return ApiKeyAuthenticationResult(api_key=api_key, user_id=api_key.user_id)

    def authenticate(self, raw_token: str) -> AuthenticatedPrincipal | None:
        """Adapter for the auth pipeline; return a principal or ``None``."""

        try:
            result = self.authenticate_token(raw_token)
        except (
            InvalidApiKeyFormatError,
            ApiKeyNotFoundError,
            ApiKeyExpiredError,
            ApiKeyRevokedError,
            ApiKeyOwnerInactiveError,
        ) as exc:
            raise AuthenticationError(str(exc)) from exc

        api_key = result.api_key
        owner = getattr(api_key, "user", None)
        principal_type = (
            PrincipalType.SERVICE_ACCOUNT
            if getattr(owner, "is_service_account", False)
            else PrincipalType.USER
        )
        return AuthenticatedPrincipal(
            user_id=result.user_id,
            principal_type=principal_type,
            auth_via=AuthVia.API_KEY,
            api_key_id=api_key.id,
        )


__all__ = [
    "ApiKeyService",
    "ApiKeyCreateResult",
    "ApiKeyAuthenticationResult",
    "ApiKeyNotFoundError",
    "ApiKeyAccessDeniedError",
    "ApiKeyRevokedError",
    "ApiKeyExpiredError",
    "ApiKeyOwnerInactiveError",
    "InvalidApiKeyFormatError",
]
