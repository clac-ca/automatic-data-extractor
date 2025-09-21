"""Authentication API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..services import auth as auth_service
from ..db import get_db
from ..models import User, UserSession
from ..schemas import AuthSessionResponse, SessionSummary, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
basic_auth = HTTPBasic(auto_error=False)


def _request_metadata(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


def _user_profile(user: User) -> UserProfile:
    return UserProfile.model_validate(user)


def _session_summary(session_model: UserSession | None) -> SessionSummary | None:
    if session_model is None:
        return None
    return SessionSummary(session_id=session_model.session_id, expires_at=session_model.expires_at)


def _available_modes(settings: config.Settings) -> list[str]:
    if settings.auth_disabled:
        return ["none"]

    configured = settings.auth_mode_sequence
    modes: list[str] = []
    if "basic" in configured:
        modes.append("basic")
    if "sso" in configured:
        modes.append("sso")
    modes.append("api-key")
    return modes


def _auth_response(
    user: User,
    settings: config.Settings,
    *,
    session_model: UserSession | None = None,
) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=_user_profile(user),
        modes=_available_modes(settings),
        session=_session_summary(session_model),
    )


def _get_user_by_email(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.execute(statement).scalar_one_or_none()


def _set_session_cookie(response: Response, settings: config.Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_same_site,
        domain=settings.session_cookie_domain,
        path=settings.session_cookie_path,
    )


def _clear_session_cookie(response: Response, settings: config.Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.session_cookie_domain,
        path=settings.session_cookie_path,
    )


@router.post(
    "/login/basic",
    response_model=AuthSessionResponse,
    openapi_extra={"security": []},
)
def login_basic(  # noqa: PLR0915 - clarity over cleverness
    request: Request,
    response: Response,
    credentials: HTTPBasicCredentials | None = Depends(basic_auth),
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    settings = config.get_settings()
    if "basic" not in settings.auth_mode_sequence:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="HTTP Basic authentication is not enabled",
        )

    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="HTTP Basic credentials required",
            headers={"WWW-Authenticate": 'Basic realm="ADE"'},
        )

    email = credentials.username.strip().lower()
    password = credentials.password or ""

    user = _get_user_by_email(db, email)
    if user is None or not user.password_hash:
        auth_service.login_failure(db, email=email, mode="basic", source="api", reason="unknown-user")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        auth_service.login_failure(db, email=email, mode="basic", source="api", reason="inactive")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    if not auth_service.verify_password(password, user.password_hash):
        auth_service.login_failure(db, email=email, mode="basic", source="api", reason="invalid-password")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    ip_address, user_agent = _request_metadata(request)

    session_model, raw_token = auth_service.complete_login(
        db,
        settings,
        user,
        mode="basic",
        source="api",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    _set_session_cookie(response, settings, raw_token)
    auth_service.set_request_auth_context(
        request,
        auth_service.RequestAuthContext.from_user(
            user,
            mode="session",
            session_id=session_model.session_id,
        ),
    )
    return _auth_response(user, settings, session_model=session_model)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    openapi_extra={"security": []},
)
def logout(
    request: Request,
    response: Response,
    identity: auth_service.AuthenticatedIdentity = Depends(
        auth_service.get_authenticated_identity
    ),
    db: Session = Depends(get_db),
) -> Response:
    settings = config.get_settings()
    ip_address, user_agent = _request_metadata(request)

    session_model = identity.session
    if session_model is not None:
        auth_service.revoke_session(db, session_model, commit=False)
        auth_service.logout(
            db,
            identity.user,
            source="api",
            payload={"session_id": session_model.session_id, "ip": ip_address, "user_agent": user_agent},
            commit=False,
        )
        db.commit()
    _clear_session_cookie(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/session",
    response_model=AuthSessionResponse,
    openapi_extra={"security": []},
)
def session_status(
    request: Request,
    response: Response,
    identity: auth_service.AuthenticatedIdentity = Depends(
        auth_service.get_authenticated_identity
    ),
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    settings = config.get_settings()
    cookie_value = request.cookies.get(settings.session_cookie_name)
    if not cookie_value:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session cookie missing")

    session_model = identity.session
    if session_model is None:
        _clear_session_cookie(response, settings)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Session expired")

    auth_service.session_refreshed(
        db,
        identity.user,
        source="api",
        payload={"session_id": session_model.session_id},
        commit=False,
    )
    db.commit()
    _set_session_cookie(response, settings, cookie_value)
    return _auth_response(identity.user, settings, session_model=session_model)


@router.get(
    "/me",
    response_model=AuthSessionResponse,
    openapi_extra={"security": []},
)
def current_user_profile(
    identity: auth_service.AuthenticatedIdentity = Depends(
        auth_service.get_authenticated_identity
    ),
) -> AuthSessionResponse:
    settings = config.get_settings()
    return _auth_response(identity.user, settings, session_model=identity.session)


@router.get(
    "/sso/login",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    openapi_extra={"security": []},
)
def sso_login() -> Response:
    settings = config.get_settings()
    if "sso" not in settings.auth_mode_sequence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO is not enabled")
    location = auth_service.build_authorization_url(settings)
    response = Response(status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.headers["Location"] = location
    return response


@router.get(
    "/sso/callback",
    response_model=AuthSessionResponse,
    openapi_extra={"security": []},
)
def sso_callback(
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    settings = config.get_settings()
    if "sso" not in settings.auth_mode_sequence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO is not enabled")
    try:
        user, claims = auth_service.exchange_code(settings, code=code, state=state, db=db)
    except auth_service.SSOExchangeError as exc:
        logger.warning("SSO code exchange failed", extra={"reason": str(exc)})
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ip_address, user_agent = _request_metadata(request)
    subject = claims.get("sub")
    session_model, raw_token = auth_service.complete_login(
        db,
        settings,
        user,
        mode="sso",
        source="api",
        ip_address=ip_address,
        user_agent=user_agent,
        subject=subject,
        include_subject=True,
    )
    _set_session_cookie(response, settings, raw_token)
    auth_service.set_request_auth_context(
        request,
        auth_service.RequestAuthContext.from_user(
            user,
            mode="session",
            session_id=session_model.session_id,
            subject=subject,
        ),
    )
    return _auth_response(user, settings, session_model=session_model)
