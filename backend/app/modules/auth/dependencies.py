"""FastAPI dependencies for authentication flows."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.service import service_dependency
from ...db.session import get_session
from ..users.models import User, UserRole
from .service import AuthService


_bearer_scheme = HTTPBearer(auto_error=False)

get_auth_service = service_dependency(AuthService)


async def bind_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    service: AuthService = Depends(get_auth_service),
) -> User:
    """Resolve the authenticated user and attach it to the request state."""

    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        payload = service.decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = await service.resolve_user(payload)
    request.state.current_user = user
    return user


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
    "bind_current_user",
    "get_auth_service",
    "require_authenticated_user",
    "require_admin_user",
]
