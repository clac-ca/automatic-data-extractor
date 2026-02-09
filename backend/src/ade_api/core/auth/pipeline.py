"""Request authentication pipeline used by FastAPI dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from fastapi import Request, WebSocket
from sqlalchemy.orm import Session

from ade_api.settings import Settings

from .errors import AuthenticationError
from .principal import AuthenticatedPrincipal, AuthVia, PrincipalType


@runtime_checkable
class ApiKeyAuthenticator(Protocol):
    """Interface for authenticating API key strings."""

    def authenticate(self, raw_token: str) -> AuthenticatedPrincipal | None: ...


@runtime_checkable
class CookieAuthenticator(Protocol):
    """Interface for authenticating cookie-backed sessions."""

    def authenticate(self, token: str) -> AuthenticatedPrincipal | None: ...


def dev_principal(settings: Settings) -> AuthenticatedPrincipal:
    """Return a synthetic principal for AUTH_DISABLED mode."""

    seed = settings.auth_disabled_user_email or "developer@example.com"
    synthetic_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ade-dev:{seed}")
    return AuthenticatedPrincipal(
        user_id=synthetic_id,
        principal_type=PrincipalType.USER,
        auth_via=AuthVia.DEV,
        email=seed,
    )


def _extract_api_key(request: Request) -> str | None:
    """Parse API key from ``X-API-Key`` only."""

    candidate = request.headers.get("x-api-key")
    return candidate.strip() if candidate else None


def _extract_api_key_from_headers(headers: Mapping[str, str]) -> str | None:
    candidate = headers.get("x-api-key")
    return candidate.strip() if candidate else None


def reset_auth_state() -> None:
    """Clear process-local auth caches (useful for tests)."""
    return


def _ensure_active_principal(
    *,
    principal: AuthenticatedPrincipal,
    session: Session,
) -> None:
    """Ensure the backing user exists and is active."""

    from ade_db.models import User

    user = session.get(User, principal.user_id)
    if user is None:
        raise AuthenticationError("Unknown principal")
    if not getattr(user, "is_active", True):
        raise AuthenticationError("User account is inactive.")


def authenticate_request(
    request: Request,
    _db: Session,  # kept for future interfaces and parity with feature services
    settings: Settings,
    api_key_service: ApiKeyAuthenticator,
    cookie_service: CookieAuthenticator,
) -> AuthenticatedPrincipal:
    """Authenticate an incoming request to a principal.

    This is deliberately a thin orchestrator: it delegates credential handling
    to injected services so auth/API key implementations can evolve
    independently.
    """

    if settings.auth_disabled:
        return dev_principal(settings)

    raw_api_key = _extract_api_key(request)
    if raw_api_key:
        principal = api_key_service.authenticate(raw_api_key)
        if principal is not None:
            _ensure_active_principal(principal=principal, session=_db)
            return principal

    cookie_token = (request.cookies.get(settings.session_cookie_name) or "").strip()
    if cookie_token:
        principal = cookie_service.authenticate(cookie_token)
        if principal is not None:
            _ensure_active_principal(principal=principal, session=_db)
            return principal

    raise AuthenticationError("Authentication required")


def authenticate_websocket(
    websocket: WebSocket,
    _db: Session,
    settings: Settings,
    api_key_service: ApiKeyAuthenticator,
    cookie_service: CookieAuthenticator,
) -> AuthenticatedPrincipal:
    """Authenticate a WebSocket connection to a principal."""

    if settings.auth_disabled:
        return dev_principal(settings)

    raw_api_key = _extract_api_key_from_headers(websocket.headers)
    if raw_api_key:
        principal = api_key_service.authenticate(raw_api_key)
        if principal is not None:
            _ensure_active_principal(principal=principal, session=_db)
            return principal

    cookie_token = (websocket.cookies.get(settings.session_cookie_name) or "").strip()
    if cookie_token:
        principal = cookie_service.authenticate(cookie_token)
        if principal is not None:
            _ensure_active_principal(principal=principal, session=_db)
            return principal

    query_token = (websocket.query_params.get("access_token") or "").strip()
    if query_token:
        principal = cookie_service.authenticate(query_token)
        if principal is not None:
            _ensure_active_principal(principal=principal, session=_db)
            return principal

    raise AuthenticationError("Authentication required")
