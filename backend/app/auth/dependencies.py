"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db, get_sessionmaker
from ..models import ApiKey, User, UserRole, UserSession
from . import api_keys, sessions

_WWW_AUTH_HEADER = 'Bearer realm="ADE"'

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


def _extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, credentials = get_authorization_scheme_param(header)
    if scheme.lower() != "bearer" or not credentials:
        return None
    return credentials


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


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = config.get_settings()
    if settings.auth_disabled:
        _set_request_context(request, _OPEN_ACCESS_USER, "none")
        return _OPEN_ACCESS_USER

    ip_address, user_agent = _client_context(request)
    cookie_value = request.cookies.get(settings.session_cookie_name)
    session_error: HTTPException | None = None

    if cookie_value:
        session_model = sessions.get_session(db, cookie_value)
        if session_model:
            user = db.get(User, session_model.user_id)
            if user and user.is_active:
                session_factory = get_sessionmaker()
                with session_factory() as metadata_db:
                    persistent = metadata_db.get(UserSession, session_model.session_id)
                    if persistent is not None:
                        refreshed = sessions.touch_session(
                            metadata_db,
                            persistent,
                            settings=settings,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            commit=True,
                        )
                    else:
                        refreshed = None
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
            session_factory = get_sessionmaker()
            with session_factory() as metadata_db:
                persistent = metadata_db.get(UserSession, session_model.session_id)
                if persistent is not None:
                    sessions.revoke_session(metadata_db, persistent, commit=True)
        else:
            session_factory = get_sessionmaker()
            with session_factory() as metadata_db:
                token_hash = sessions.hash_session_token(cookie_value)
                orphan = (
                    metadata_db.query(UserSession)
                    .filter(UserSession.token_hash == token_hash)
                    .one_or_none()
                )
                if orphan is not None:
                    sessions.revoke_session(metadata_db, orphan, commit=True)
        db.rollback()
        session_error = HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Invalid session token",
        )

    token = _extract_bearer_token(request)
    if token is not None:
        api_key = api_keys.get_api_key(db, token)
        if api_key is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )

        user = db.get(User, api_key.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )

        session_factory = get_sessionmaker()
        with session_factory() as metadata_db:
            persistent = metadata_db.get(ApiKey, api_key.api_key_id)
            if persistent is None:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="Invalid API key",
                )
            api_keys.touch_api_key_usage(metadata_db, persistent, commit=True)
        request.state.api_key = persistent
        _set_request_context(
            request,
            user,
            "api-key",
            api_key_id=api_key.api_key_id,
        )
        db.commit()
        return user

    if session_error is not None:
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
