"""FastAPI dependencies for authentication flows."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.service import service_dependency
from ...db.session import get_session
from ..users.models import User, UserRole
from .service import AuthenticatedIdentity, AuthService

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

get_auth_service = service_dependency(AuthService)


async def bind_current_principal(
    request: Request,
    _session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    api_key: Annotated[str | None, Depends(_api_key_scheme)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedIdentity:
    """Resolve the authenticated identity and attach it to the request state."""

    if credentials is not None:
        try:
            payload = service.decode_token(credentials.credentials, expected_type="access")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        user = await service.resolve_user(payload)
        request.state.current_user = user
        return AuthenticatedIdentity(user=user, credentials="bearer_token")

    session_cookie = request.cookies.get(service.settings.session_cookie_name)
    if session_cookie:
        try:
            payload = service.decode_token(session_cookie, expected_type="access")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
        service.enforce_csrf(request, payload)
        user = await service.resolve_user(payload)
        request.state.current_user = user
        return AuthenticatedIdentity(user=user, credentials="session_cookie")

    if api_key:
        identity = await service.authenticate_api_key(api_key)
        request.state.current_user = identity.user
        return identity

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def bind_current_user(
    principal: Annotated[AuthenticatedIdentity, Depends(bind_current_principal)],
) -> User:
    """Resolve the authenticated user principal or reject service account credentials."""

    user = principal.user
    if user.is_service_account:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="User credentials required",
        )
    return user


async def require_authenticated_user(
    user: Annotated[User, Depends(bind_current_user)]
) -> User:
    """Dependency alias that ensures the user is authenticated."""

    return user


async def require_admin_user(
    user: Annotated[User, Depends(bind_current_user)]
) -> User:
    """Ensure the authenticated user holds the administrator role."""

    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
    return user


__all__ = [
    "bind_current_principal",
    "bind_current_user",
    "get_auth_service",
    "require_authenticated_user",
    "require_admin_user",
]
