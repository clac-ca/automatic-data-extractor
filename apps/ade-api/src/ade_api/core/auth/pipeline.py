"""Request authentication pipeline used by FastAPI dependencies."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from fastapi import Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.settings import Settings

from .errors import AuthenticationError
from .principal import AuthenticatedPrincipal, AuthVia, PrincipalType

logger = logging.getLogger(__name__)
_ADMIN_ROLE_SLUG = "global-admin"


@runtime_checkable
class ApiKeyAuthenticator(Protocol):
    """Interface for authenticating API key strings."""

    async def authenticate(self, raw_token: str) -> AuthenticatedPrincipal | None: ...


@runtime_checkable
class SessionAuthenticator(Protocol):
    """Interface for authenticating browser/CLI sessions."""

    async def authenticate(self, request: Request) -> AuthenticatedPrincipal | None: ...


def _dev_principal(settings: Settings) -> AuthenticatedPrincipal:
    """Return a synthetic principal for AUTH_DISABLED mode."""

    seed = settings.auth_disabled_user_email or "developer@example.com"
    synthetic_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ade-dev:{seed}")
    return AuthenticatedPrincipal(
        user_id=synthetic_id,
        principal_type=PrincipalType.USER,
        auth_via=AuthVia.DEV,
    )


def _extract_api_key(request: Request) -> str | None:
    """Parse API key from standard headers."""

    header = request.headers.get("authorization") or ""
    match = re.match(r"^api-key\s+(?P<token>.+)$", header, flags=re.IGNORECASE)
    if match:
        return match.group("token").strip() or None
    candidate = request.headers.get("x-api-key")
    return candidate.strip() if candidate else None


def _extract_api_key_from_headers(headers: Mapping[str, str]) -> str | None:
    header = headers.get("authorization") or ""
    match = re.match(r"^api-key\s+(?P<token>.+)$", header, flags=re.IGNORECASE)
    if match:
        return match.group("token").strip() or None
    candidate = headers.get("x-api-key")
    return candidate.strip() if candidate else None


_dev_user_lock = asyncio.Lock()
_dev_user_ready: set[uuid.UUID] = set()


def reset_auth_state() -> None:
    """Clear process-local auth caches (useful for tests)."""

    _dev_user_ready.clear()


async def _ensure_dev_user(
    principal: AuthenticatedPrincipal,
    settings: Settings,
    session: AsyncSession,
) -> None:
    """Ensure a backing User exists for auth-disabled mode (once per process)."""

    # Deferred import avoids circular dependency during app startup.
    from ade_api.models import User

    if principal.user_id in _dev_user_ready:
        return

    async with _dev_user_lock:
        if principal.user_id in _dev_user_ready:
            return

        user = await session.get(User, principal.user_id)
        if user is None:
            alias = settings.auth_disabled_user_email or "developer@example.com"
            user = User(
                id=principal.user_id,
                email=alias,
                display_name=settings.auth_disabled_user_name,
                is_service_account=False,
                is_active=True,
            )
            session.add(user)
            await session.flush()

        try:
            from ade_api.core.rbac.types import ScopeType
            from ade_api.features.rbac import RbacService

            rbac = RbacService(session=session)
            await rbac.sync_system_roles()
            admin_role = await rbac.get_role_by_slug(slug=_ADMIN_ROLE_SLUG)
            if admin_role is not None:
                await rbac.assign_role_if_missing(
                    user_id=principal.user_id,
                    role_id=admin_role.id,
                    scope_type=ScopeType.GLOBAL,
                    scope_id=None,
                )
        except Exception:
            logger.warning(
                "auth.dev_user.bootstrap_failed",
                exc_info=True,
                extra={"user_id": str(principal.user_id)},
            )
            return

        _dev_user_ready.add(principal.user_id)


async def _ensure_active_principal(
    *,
    principal: AuthenticatedPrincipal,
    session: AsyncSession,
) -> None:
    """Ensure the backing user exists and is active."""

    from ade_api.models import User

    user = await session.get(User, principal.user_id)
    if user is None:
        raise AuthenticationError("Unknown principal")
    if not getattr(user, "is_active", True):
        raise AuthenticationError("User account is inactive.")


async def authenticate_request(
    request: Request,
    _db: AsyncSession,  # kept for future interfaces and parity with feature services
    settings: Settings,
    api_key_service: ApiKeyAuthenticator,
    session_service: SessionAuthenticator,
) -> AuthenticatedPrincipal:
    """Authenticate an incoming request to a principal.

    This is deliberately a thin orchestrator: it delegates credential handling
    to injected services so auth/API key implementations can evolve
    independently.
    """

    if settings.auth_disabled:
        principal = _dev_principal(settings)
        await _ensure_dev_user(principal, settings, _db)
        await _ensure_active_principal(principal=principal, session=_db)
        return principal

    raw_api_key = _extract_api_key(request)
    if raw_api_key:
        principal = await api_key_service.authenticate(raw_api_key)
        if principal is not None:
            await _ensure_active_principal(principal=principal, session=_db)
            return principal

    principal = await session_service.authenticate(request)
    if principal is not None:
        await _ensure_active_principal(principal=principal, session=_db)
        return principal

    raise AuthenticationError("Authentication required")


async def authenticate_websocket(
    websocket: WebSocket,
    _db: AsyncSession,
    settings: Settings,
    api_key_service: ApiKeyAuthenticator,
) -> AuthenticatedPrincipal:
    """Authenticate a WebSocket connection to a principal."""

    if settings.auth_disabled:
        principal = _dev_principal(settings)
        await _ensure_dev_user(principal, settings, _db)
        await _ensure_active_principal(principal=principal, session=_db)
        return principal

    raw_api_key = _extract_api_key_from_headers(websocket.headers)
    if raw_api_key:
        principal = await api_key_service.authenticate(raw_api_key)
        if principal is not None:
            await _ensure_active_principal(principal=principal, session=_db)
            return principal

    auth_header = websocket.headers.get("authorization") or ""
    scheme, _, token = auth_header.partition(" ")
    candidate = token.strip() if scheme.lower() == "bearer" else ""
    if not candidate:
        candidate = (websocket.query_params.get("access_token") or "").strip()
    if not candidate:
        candidate = (websocket.cookies.get(settings.session_cookie_name) or "").strip()

    if candidate:
        from ade_api.features.auth.service import AuthService

        service = AuthService(session=_db, settings=settings)
        principal = await service.resolve_principal_from_access_token(candidate)
        if principal is not None:
            await _ensure_active_principal(principal=principal, session=_db)
            return principal

        raise AuthenticationError("Authentication required")

    raise AuthenticationError("Authentication required")
