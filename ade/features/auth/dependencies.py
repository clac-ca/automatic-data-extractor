"""FastAPI dependencies for authentication flows."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import (
    APIKeyCookie,
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ade.api.settings import get_app_settings
from ade.settings import Settings
from ade.db.session import get_session

from ade.features.roles.service import ensure_user_principal

from ..users.models import User
from .service import AuthenticatedIdentity, AuthService

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_session_cookie_scheme = APIKeyCookie(
    name="ade_session",
    scheme_name="SessionCookie",
    auto_error=False,
)


def configure_auth_dependencies(*, settings: Settings) -> None:
    """Configure authentication dependency state for the application lifecycle."""

    _session_cookie_scheme.model.name = settings.session_cookie_name

async def get_current_identity(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer_scheme)
    ],
    api_key: Annotated[str | None, Security(_api_key_scheme)],
    session_cookie: Annotated[str | None, Security(_session_cookie_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AuthenticatedIdentity:
    """Resolve the authenticated identity for the request."""

    service = AuthService(session=session, settings=settings)
    if credentials is not None:
        try:
            payload = service.decode_token(credentials.credentials, expected_type="access")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        user = await service.resolve_user(payload)
        principal = await ensure_user_principal(session=session, user=user)
        return AuthenticatedIdentity(
            user=user,
            principal=principal,
            credentials="bearer_token",
        )

    cookie_value = session_cookie or request.cookies.get(
        service.settings.session_cookie_name
    )
    if cookie_value:
        try:
            payload = service.decode_token(cookie_value, expected_type="access")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
        service.enforce_csrf(request, payload)
        user = await service.resolve_user(payload)
        principal = await ensure_user_principal(session=session, user=user)
        return AuthenticatedIdentity(
            user=user,
            principal=principal,
            credentials="session_cookie",
        )

    if api_key:
        identity = await service.authenticate_api_key(api_key, request=request)
        return identity

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def get_current_user(
    principal: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
) -> User:
    """Resolve the authenticated user principal."""

    user = principal.user
    return user


async def require_authenticated_user(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Dependency alias that ensures the user is authenticated."""

    return user


__all__ = [
    "get_current_identity",
    "get_current_user",
    "configure_auth_dependencies",
    "require_authenticated_user",
]
