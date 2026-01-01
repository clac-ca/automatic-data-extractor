"""Domain service for API key lifecycle and authentication."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.listing import ListPage, paginate_query
from ade_api.common.types import OrderBy
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

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def create_for_user(
        self,
        *,
        user_id: UUID,
        name: str | None,
        expires_in_days: int | None,
    ) -> ApiKeyCreateResult:
        """Create a new API key for the specified owner."""

        owner = await self._get_user(user_id=user_id)
        return await self._create_api_key(
            user_id=owner.id,
            name=name,
            expires_in_days=expires_in_days,
        )

    async def _get_user(self, *, user_id: UUID) -> User:
        owner = await self._session.get(User, user_id)
        if owner is None:
            raise ValueError("Owner user not found")
        if not owner.is_active:
            raise ValueError("Owner user is inactive")
        return owner

    async def _create_api_key(
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
        await self._session.flush()
        await self._session.refresh(api_key)

        secret = f"{prefix}.{secret_part}"
        return ApiKeyCreateResult(api_key=api_key, secret=secret)

    # -- Listing ----------------------------------------------------------

    def _base_query(self) -> Select[tuple[ApiKey]]:
        return select(ApiKey)

    async def list_for_user(
        self,
        *,
        user_id: UUID,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        order_by: OrderBy,
        page: int,
        per_page: int,
    ) -> ListPage[ApiKey]:
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

        return await paginate_query(
            self._session,
            stmt,
            page=page,
            per_page=per_page,
            order_by=order_by,
            changes_cursor="0",
        )

    async def list_all(
        self,
        *,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        order_by: OrderBy,
        user_id: UUID | None,
        page: int,
        per_page: int,
    ) -> ListPage[ApiKey]:
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

        return await paginate_query(
            self._session,
            stmt,
            page=page,
            per_page=per_page,
            order_by=order_by,
            changes_cursor="0",
        )

    # -- Read / revoke ----------------------------------------------------

    async def get_by_id(self, api_key_id: UUID) -> ApiKey:
        result = await self._session.execute(self._base_query().where(ApiKey.id == api_key_id))
        api_key = result.scalar_one_or_none()
        if api_key is None:
            raise ApiKeyNotFoundError(f"API key {api_key_id} not found")
        return api_key

    async def revoke(self, api_key_id: UUID) -> ApiKey:
        api_key = await self.get_by_id(api_key_id)
        if api_key.revoked_at is not None:
            return api_key
        api_key.revoked_at = utc_now()
        await self._session.flush()
        await self._session.refresh(api_key)
        return api_key

    async def revoke_for_user(
        self,
        *,
        api_key_id: UUID,
        user_id: UUID,
    ) -> ApiKey:
        """Revoke a key ensuring it belongs to a specific user."""

        api_key = await self.get_by_id(api_key_id)
        if api_key.user_id != user_id:
            raise ApiKeyAccessDeniedError(
                f"API key {api_key_id} is not owned by user {user_id}"
            )
        if api_key.revoked_at is not None:
            return api_key
        api_key.revoked_at = utc_now()
        await self._session.flush()
        await self._session.refresh(api_key)
        return api_key

    async def revoke_all_for_user(self, *, user_id: UUID) -> None:
        """Revoke all API keys owned by the specified user."""

        now = utc_now()
        await self._session.execute(
            sa.update(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self._session.flush()

    # -- Authentication ---------------------------------------------------

    async def authenticate_token(
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

        result = await self._session.execute(
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
            user = await self._session.get(User, api_key.user_id)
        if user is None:
            raise ApiKeyNotFoundError("API key not recognized")
        if not user.is_active:
            raise ApiKeyOwnerInactiveError("API key owner is inactive")

        if touch_usage:
            api_key.last_used_at = now
            await self._session.flush()

        return ApiKeyAuthenticationResult(api_key=api_key, user_id=api_key.user_id)

    async def authenticate(self, raw_token: str) -> AuthenticatedPrincipal | None:
        """Adapter for the auth pipeline; return a principal or ``None``."""

        try:
            result = await self.authenticate_token(raw_token)
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
