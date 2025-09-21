"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyCookie, APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import User, UserRole, UserSession
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
    session_error: HTTPException | None = None
    pending_commit = False

    if cookie_value:
        session_model = service.get_session(db, cookie_value)
        if session_model:
            user = db.get(User, session_model.user_id)
            if user and user.is_active:
                refreshed = service.touch_session(
                    db,
                    session_model,
                    settings=settings,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    commit=False,
                )
                if refreshed is not None:
                    request.state.auth_session = refreshed
                    _set_request_context(
                        request,
                        user,
                        "session",
                        session_id=refreshed.session_id,
                    )
                    db.commit()
                    return user
                service.revoke_session(db, session_model, commit=False)
                pending_commit = True
            else:
                service.revoke_session(db, session_model, commit=False)
                pending_commit = True
        else:
            token_hash = service.hash_session_token(cookie_value)
            orphan = (
                db.query(UserSession)
                .filter(UserSession.token_hash == token_hash)
                .one_or_none()
            )
            if orphan is not None:
                service.revoke_session(db, orphan, commit=False)
                pending_commit = True
        session_error = HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Invalid session token",
        )

    if api_key_token is not None:
        api_key = service.get_api_key(db, api_key_token)
        if api_key is None:
            if pending_commit:
                db.commit()
            else:
                db.rollback()
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )

        user = db.get(User, api_key.user_id)
        if user is None or not user.is_active:
            if pending_commit:
                db.commit()
            else:
                db.rollback()
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )

        updated_api_key = service.touch_api_key_usage(db, api_key, commit=False)
        request.state.api_key = updated_api_key
        _set_request_context(
            request,
            user,
            "api-key",
            api_key_id=api_key.api_key_id,
        )
        db.commit()
        return user

    if session_error is not None:
        if pending_commit:
            db.commit()
        else:
            db.rollback()
        raise session_error

    db.rollback()
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": _WWW_AUTH_HEADER},
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
