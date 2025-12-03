"""Domain service for API key lifecycle and authentication."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.pagination import Page, paginate_sql
from ade_api.common.time import utc_now
from ade_api.core.auth.errors import AuthenticationError
from ade_api.core.auth.principal import AuthenticatedPrincipal, AuthVia, PrincipalType
from ade_api.core.models import ApiKey, User, Workspace
from ade_api.core.rbac.types import ScopeType
from ade_api.core.security.api_keys import (
    generate_api_key_prefix,
    generate_api_key_secret,
    hash_api_key_secret,
)
from ade_api.settings import Settings


@dataclass(slots=True)
class ApiKeyCreateResult:
    """Result returned when a new API key is created."""

    api_key: ApiKey
    secret: str  # full secret, e.g. "prefix.secret"


@dataclass(slots=True)
class ApiKeyAuthenticationResult:
    """Result of authenticating a raw API key."""

    api_key: ApiKey
    owner_user_id: UUID


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


def _canonical_email(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        msg = "Email must not be empty"
        raise ValueError(msg)
    return cleaned.lower()


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
        owner_user_id: UUID | None = None,
        email: str | None = None,
        created_by_user_id: UUID | None,
        label: str | None,
        expires_in_days: int | None,
        scope_type: ScopeType,
        scope_id: UUID | None,
    ) -> ApiKeyCreateResult:
        """Create a new API key for the specified owner."""

        owner = await self._get_owner(owner_user_id=owner_user_id, email=email)
        return await self._create_api_key(
            owner_user_id=owner.id,
            created_by_user_id=created_by_user_id,
            label=label,
            expires_in_days=expires_in_days,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    async def _get_owner(
        self, *, owner_user_id: UUID | None, email: str | None
    ) -> User:
        provided = [owner_user_id, email]
        if sum(value is not None for value in provided) != 1:
            msg = "Provide exactly one of owner_user_id or email"
            raise ValueError(msg)

        if owner_user_id is not None:
            owner = await self._session.get(User, owner_user_id)
        else:
            assert email is not None
            canonical_email = _canonical_email(email)
            result = await self._session.execute(
                select(User).where(User.email_canonical == canonical_email)
            )
            owner = result.scalar_one_or_none()

        if owner is None:
            raise ValueError("Owner user not found")
        if not owner.is_active:
            raise ValueError("Owner user is inactive")
        return owner

    async def _create_api_key(
        self,
        *,
        owner_user_id: UUID,
        created_by_user_id: UUID | None,
        label: str | None,
        expires_in_days: int | None,
        scope_type: ScopeType,
        scope_id: UUID | None,
    ) -> ApiKeyCreateResult:
        label = _normalize_label(label)

        if scope_type == ScopeType.GLOBAL and scope_id is not None:
            msg = "scope_id must be null when scope_type=global"
            raise ValueError(msg)
        if scope_type == ScopeType.WORKSPACE and scope_id is None:
            msg = "scope_id is required when scope_type=workspace"
            raise ValueError(msg)

        if scope_type == ScopeType.WORKSPACE and scope_id is not None:
            _workspace = await self._session.get(Workspace, scope_id)
            if _workspace is None:
                raise ValueError("Workspace not found for scope_id")

        expires_at: datetime | None = None
        if expires_in_days is not None:
            expires_at = utc_now() + timedelta(days=expires_in_days)

        prefix_length = getattr(self._settings, "api_key_prefix_length", 12)
        secret_bytes = getattr(self._settings, "api_key_secret_bytes", 32)
        prefix = generate_api_key_prefix(prefix_length)
        secret_part = generate_api_key_secret(secret_bytes)
        token_hash = hash_api_key_secret(secret_part)

        api_key = ApiKey(
            owner_user_id=owner_user_id,
            created_by_user_id=created_by_user_id,
            token_prefix=prefix,
            token_hash=token_hash,
            label=label,
            scope_type=scope_type,
            scope_id=scope_id,
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

    def _apply_revoked_filter(
        self,
        stmt: Select[tuple[ApiKey]],
        *,
        include_revoked: bool,
    ) -> Select[tuple[ApiKey]]:
        if not include_revoked:
            stmt = stmt.where(ApiKey.revoked_at.is_(None))
        return stmt

    async def list_for_owner(
        self,
        *,
        owner_user_id: UUID,
        include_revoked: bool,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[ApiKey]:
        """List keys for a specific owner (self-service and admin use)."""

        stmt = (
            self._base_query()
            .where(ApiKey.owner_user_id == owner_user_id)
            .order_by(ApiKey.created_at.desc())
        )
        stmt = self._apply_revoked_filter(stmt, include_revoked=include_revoked)

        return await paginate_sql(
            self._session,
            stmt,
            page=page,
            page_size=page_size,
            include_total=include_total,
            order_by=(ApiKey.created_at.desc(), ApiKey.id.desc()),
        )

    async def list_all(
        self,
        *,
        include_revoked: bool,
        owner_user_id: UUID | None,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[ApiKey]:
        """List keys across the tenant (admin use)."""

        stmt = self._base_query().order_by(ApiKey.created_at.desc())
        if owner_user_id is not None:
            stmt = stmt.where(ApiKey.owner_user_id == owner_user_id)
        stmt = self._apply_revoked_filter(stmt, include_revoked=include_revoked)

        return await paginate_sql(
            self._session,
            stmt,
            page=page,
            page_size=page_size,
            include_total=include_total,
            order_by=(ApiKey.created_at.desc(), ApiKey.id.desc()),
        )

    # -- Read / revoke ----------------------------------------------------

    async def get_by_id(self, api_key_id: UUID) -> ApiKey:
        result = await self._session.execute(
            self._base_query().where(ApiKey.id == api_key_id)
        )
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

    async def revoke_for_owner(
        self,
        *,
        api_key_id: UUID,
        owner_user_id: UUID,
    ) -> ApiKey:
        """Revoke a key ensuring it belongs to a specific owner."""

        api_key = await self.get_by_id(api_key_id)
        if api_key.owner_user_id != owner_user_id:
            raise ApiKeyAccessDeniedError(
                f"API key {api_key_id} is not owned by user {owner_user_id}"
            )
        if api_key.revoked_at is not None:
            return api_key
        api_key.revoked_at = utc_now()
        await self._session.flush()
        await self._session.refresh(api_key)
        return api_key

    async def revoke_all_for_owner(self, *, owner_user_id: UUID) -> None:
        """Revoke all API keys owned by the specified user."""

        now = utc_now()
        await self._session.execute(
            sa.update(ApiKey)
            .where(ApiKey.owner_user_id == owner_user_id, ApiKey.revoked_at.is_(None))
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
            .where(ApiKey.token_prefix == prefix)
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

        expected_hash = api_key.token_hash
        candidate_hash = hash_api_key_secret(secret)
        if not secrets.compare_digest(expected_hash, candidate_hash):
            raise ApiKeyNotFoundError("API key not recognized")

        owner = getattr(api_key, "owner", None)
        if owner is None:
            owner = await self._session.get(User, api_key.owner_user_id)
        if owner is None:
            raise ApiKeyNotFoundError("API key not recognized")
        if not owner.is_active:
            raise ApiKeyOwnerInactiveError("API key owner is inactive")

        if touch_usage:
            api_key.last_used_at = now
            await self._session.flush()

        return ApiKeyAuthenticationResult(api_key=api_key, owner_user_id=api_key.owner_user_id)

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
        owner = getattr(api_key, "owner", None)
        principal_type = (
            PrincipalType.SERVICE_ACCOUNT
            if getattr(owner, "is_service_account", False)
            else PrincipalType.USER
        )
        return AuthenticatedPrincipal(
            user_id=result.owner_user_id,
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
