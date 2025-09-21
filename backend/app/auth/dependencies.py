"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyCookie, APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import User, UserRole
from . import service

_WWW_AUTH_HEADER = 'Bearer realm="ADE"'

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Synthetic admin identity returned when ADE_AUTH_MODES=none.
_OPEN_ACCESS_USER = User(
    user_id="00000000000000000000000000",
    email="open-access@ade.local",
    password_hash=None,
    role=UserRole.ADMIN,
    is_active=True,
)
_OPEN_ACCESS_USER.created_at = "1970-01-01T00:00:00+00:00"
_OPEN_ACCESS_USER.updated_at = "1970-01-01T00:00:00+00:00"


def _client_context(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


async def _session_cookie_value(
    request: Request,
    settings: config.Settings = Depends(config.get_settings),
) -> str | None:
    cookie = APIKeyCookie(name=settings.session_cookie_name, auto_error=False)
    token = await cookie(request)
    if token:
        return token
    return None


def _resolve_api_key_token(
    bearer_credentials: HTTPAuthorizationCredentials | None,
    header_token: str | None,
) -> str | None:
    if bearer_credentials and bearer_credentials.credentials:
        return bearer_credentials.credentials
    if header_token:
        return header_token
    return None


def _set_request_context(
    request: Request,
    user: User,
    mode: str,
    *,
    session_id: str | None = None,
    api_key_id: str | None = None,
) -> None:
    request.state.auth_context = {
        "user_id": user.user_id,
        "email": user.email,
        "mode": mode,
    }
    if session_id is not None:
        request.state.auth_context["session_id"] = session_id
    if api_key_id is not None:
        request.state.auth_context["api_key_id"] = api_key_id


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: config.Settings = Depends(config.get_settings),
    session_token: str | None = Depends(_session_cookie_value),
    bearer_credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    header_token: str | None = Depends(_api_key_header),
) -> User:
    if settings.auth_disabled:
        _set_request_context(request, _OPEN_ACCESS_USER, "none")
        return _OPEN_ACCESS_USER

    ip_address, user_agent = _client_context(request)
    cookie_value = session_token
    api_key_token = _resolve_api_key_token(bearer_credentials, header_token)
    resolution = service.resolve_credentials(
        db,
        settings,
        session_token=cookie_value,
        api_key_token=api_key_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if resolution.user is not None:
        mode = resolution.mode
        if mode is None:
            raise RuntimeError("Resolved authenticated user without an auth mode")
        if mode == "session":
            if resolution.session is not None:
                request.state.auth_session = resolution.session
                _set_request_context(
                    request,
                    resolution.user,
                    mode,
                    session_id=resolution.session.session_id,
                )
            else:
                _set_request_context(request, resolution.user, mode)
        elif mode == "api-key":
            if resolution.api_key is not None:
                request.state.api_key = resolution.api_key
                _set_request_context(
                    request,
                    resolution.user,
                    mode,
                    api_key_id=resolution.api_key.api_key_id,
                )
            else:
                _set_request_context(request, resolution.user, mode)
        else:
            _set_request_context(request, resolution.user, mode)
        return resolution.user

    failure = resolution.failure
    if failure is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": _WWW_AUTH_HEADER},
        )

    raise HTTPException(
        failure.status_code,
        detail=failure.detail,
        headers=failure.headers,
    )


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Administrator privileges required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]


__all__ = [
    "AdminUser",
    "CurrentUser",
    "get_current_user",
    "require_admin",
]
