"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Annotated

import base64

from fastapi import Depends, HTTPException, Request, status

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasicCredentials,
    HTTPBearer,
)
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import User, UserRole
from . import passwords, sessions, sso
from .sso import SSOExchangeError

_http_bearer = HTTPBearer(auto_error=False)


def _client_context(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


def _www_authenticate_header(modes: tuple[str, ...]) -> str:
    parts: list[str] = []
    if "basic" in modes:
        parts.append('Basic realm="ADE"')
    if "sso" in modes:
        parts.append('Bearer realm="ADE"')
    if not parts:
        parts.append('Basic realm="ADE"')
    return ", ".join(parts)


def extract_basic_credentials(request: Request) -> HTTPBasicCredentials | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, credentials = get_authorization_scheme_param(header)
    if scheme.lower() != "basic" or not credentials:
        return None
    try:
        decoded = base64.b64decode(credentials).decode("latin-1")
    except (ValueError, UnicodeDecodeError):
        return None
    username, _, password = decoded.partition(":")
    return HTTPBasicCredentials(username=username, password=password)


def _set_request_context(request: Request, user: User, mode: str, *, session_id: str | None = None, subject: str | None = None) -> None:
    request.state.auth_context = {
        "user_id": user.user_id,
        "email": user.email,
        "mode": mode,
    }
    if session_id is not None:
        request.state.auth_context["session_id"] = session_id
    if subject is not None:
        request.state.auth_context["subject"] = subject


def _load_user_by_email(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.execute(statement).scalar_one_or_none()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = config.get_settings()
    modes = settings.auth_mode_sequence
    ip_address, user_agent = _client_context(request)

    if "session" in modes:
        cookie_value = request.cookies.get(settings.session_cookie_name)
        if cookie_value:
            session_model = sessions.get_session(db, cookie_value)
            if session_model:
                user = db.get(User, session_model.user_id)
                if user and user.is_active:
                    sessions.touch_session(
                        db,
                        session_model,
                        settings=settings,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        commit=True,
                    )
                    request.state.auth_session = session_model
                    _set_request_context(
                        request,
                        user,
                        "session",
                        session_id=session_model.session_id,
                    )
                    return user
                if session_model:
                    sessions.revoke_session(db, session_model, commit=True)

    if "basic" in modes:
        credentials = extract_basic_credentials(request)
        if credentials is not None:
            email = credentials.username.strip().lower()
            password = credentials.password or ""
            user = _load_user_by_email(db, email)
            if user and user.is_active and user.password_hash:
                if passwords.verify_password(password, user.password_hash):
                    db.commit()
                    _set_request_context(request, user, "basic")
                    return user

    if "sso" in modes:
        bearer: HTTPAuthorizationCredentials | None = _http_bearer(request)
        if bearer is not None:
            try:
                user, claims = sso.verify_bearer_token(
                    config.get_settings(), token=bearer.credentials, db=db
                )
            except SSOExchangeError as exc:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    detail=str(exc),
                    headers={"WWW-Authenticate": _www_authenticate_header(modes)},
                ) from exc
            _set_request_context(
                request,
                user,
                "sso",
                subject=claims.get("sub"),
            )
            db.commit()
            return user

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": _www_authenticate_header(modes)},
    )


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Administrator privileges required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]


__all__ = [
    "AdminUser",
    "extract_basic_credentials",
    "CurrentUser",
    "get_current_user",
    "require_admin",
]
