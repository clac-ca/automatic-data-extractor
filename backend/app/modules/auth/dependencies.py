"""FastAPI dependencies for authentication flows."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.service import service_dependency
from ...db.session import get_session
from ..users.models import User, UserRole
from .service import (
    APIKeyPrincipalType,
    AuthenticatedPrincipal,
    AuthService,
)


_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

get_auth_service = service_dependency(AuthService)


async def bind_current_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    api_key: str | None = Depends(_api_key_scheme),
    service: AuthService = Depends(get_auth_service),
) -> AuthenticatedPrincipal:
    """Resolve the authenticated principal and attach it to the request state."""

    if credentials is not None:
        try:
            payload = service.decode_token(credentials.credentials)
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        user = await service.resolve_user(payload)
        request.state.current_user = user
        request.state.current_service_account = None
        return AuthenticatedPrincipal(
            principal_type=APIKeyPrincipalType.USER,
            user=user,
        )

    if api_key:
        principal = await service.authenticate_api_key(api_key)
        if principal.principal_type == APIKeyPrincipalType.USER:
            request.state.current_user = principal.user
            request.state.current_service_account = None
        else:
            request.state.current_user = None
            request.state.current_service_account = principal.service_account
        return principal

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def bind_current_user(
    principal: AuthenticatedPrincipal = Depends(bind_current_principal),
) -> User:
    """Resolve the authenticated user principal or reject service account credentials."""

    if principal.principal_type != APIKeyPrincipalType.USER or principal.user is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="User credentials required",
        )
    return principal.user


async def require_authenticated_user(user: User = Depends(bind_current_user)) -> User:
    """Dependency alias that ensures the user is authenticated."""

    return user


async def require_admin_user(user: User = Depends(bind_current_user)) -> User:
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
