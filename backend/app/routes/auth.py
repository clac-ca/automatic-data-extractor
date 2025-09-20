"""Authentication API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..auth import dependencies, sessions, sso
from ..auth.events import login_failure, login_success, logout as logout_event, session_refreshed
from ..auth.passwords import verify_password
from ..auth.sso import SSOExchangeError
from ..db import get_db
from ..models import User, UserSession
from ..schemas import AuthSessionResponse, SessionSummary, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


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


def _auth_response(
    user: User,
    settings: config.Settings,
    *,
    session_model: UserSession | None = None,
) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=_user_profile(user),
        modes=list(settings.auth_mode_sequence),
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


def _set_request_context(
    request: Request,
    user: User,
    *,
    mode: str,
    session_id: str | None = None,
    subject: str | None = None,
) -> None:
    request.state.auth_context = {
        "user_id": user.user_id,
        "email": user.email,
        "mode": mode,
    }
    if session_id is not None:
        request.state.auth_context["session_id"] = session_id
    if subject is not None:
        request.state.auth_context["subject"] = subject


@router.post("/login", response_model=AuthSessionResponse)
def login(  # noqa: PLR0915 - clarity over cleverness
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    settings = config.get_settings()
    modes = settings.auth_mode_sequence

    if "basic" not in modes:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="HTTP Basic authentication is not enabled",
        )

    credentials: HTTPBasicCredentials | None = dependencies.extract_basic_credentials(request)
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
        login_failure(db, email=email, mode="basic", source="api", reason="unknown-user")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        login_failure(db, email=email, mode="basic", source="api", reason="inactive")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    if not verify_password(password, user.password_hash):
        login_failure(db, email=email, mode="basic", source="api", reason="invalid-password")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    ip_address, user_agent = _request_metadata(request)
    now_iso = datetime.now(timezone.utc).isoformat()
    user.last_login_at = now_iso

    session_model, raw_token = sessions.issue_session(
        db,
        user,
        settings=settings,
        ip_address=ip_address,
        user_agent=user_agent,
        commit=False,
    )

    login_success(
        db,
        user,
        mode="basic",
        source="api",
        payload={"ip": ip_address, "user_agent": user_agent},
        commit=False,
    )

    db.commit()
    db.refresh(user)
    db.refresh(session_model)
    assert raw_token is not None  # for type checkers
    _set_session_cookie(response, settings, raw_token)
    _set_request_context(
        request,
        user,
        mode="session",
        session_id=session_model.session_id,
    )
    return _auth_response(user, settings, session_model=session_model)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    current_user=Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    settings = config.get_settings()
    cookie_value = request.cookies.get(settings.session_cookie_name)
    ip_address, user_agent = _request_metadata(request)

    if cookie_value:
        session_model = sessions.get_session(db, cookie_value)
        if session_model and session_model.user_id == current_user.user_id:
            sessions.revoke_session(db, session_model, commit=True)
            logout_event(
                db,
                current_user,
                source="api",
                payload={"session_id": session_model.session_id, "ip": ip_address, "user_agent": user_agent},
                commit=True,
            )
    _clear_session_cookie(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/session", response_model=AuthSessionResponse)
def session_status(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    settings = config.get_settings()
    cookie_value = request.cookies.get(settings.session_cookie_name)
    if not cookie_value:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session cookie missing")

    session_model = sessions.get_session(db, cookie_value)
    if session_model is None:
        _clear_session_cookie(response, settings)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = db.get(User, session_model.user_id)
    if user is None or not user.is_active:
        sessions.revoke_session(db, session_model, commit=True)
        _clear_session_cookie(response, settings)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session invalid")

    ip_address, user_agent = _request_metadata(request)
    refreshed = sessions.touch_session(
        db,
        session_model,
        settings=settings,
        ip_address=ip_address,
        user_agent=user_agent,
        commit=True,
    )
    if refreshed is None:
        sessions.revoke_session(db, session_model, commit=True)
        _clear_session_cookie(response, settings)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    session_refreshed(
        db,
        user,
        source="api",
        payload={"session_id": refreshed.session_id},
        commit=True,
    )
    _set_session_cookie(response, settings, cookie_value)
    _set_request_context(
        request,
        user,
        mode="session",
        session_id=refreshed.session_id,
    )
    return _auth_response(user, settings, session_model=refreshed)


@router.get("/me", response_model=AuthSessionResponse)
def current_user_profile(
    request: Request,
    current_user=Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    settings = config.get_settings()
    session_model = None
    cookie_value = request.cookies.get(settings.session_cookie_name)
    if cookie_value:
        candidate = sessions.get_session(db, cookie_value)
        if candidate and candidate.user_id == current_user.user_id:
            session_model = candidate
    existing = getattr(request.state, "auth_context", None)
    mode = "basic"
    subject = None
    if isinstance(existing, dict):
        mode = existing.get("mode", mode)
        subject = existing.get("subject")
    _set_request_context(
        request,
        current_user,
        mode=mode,
        session_id=session_model.session_id if session_model else None,
        subject=subject,
    )
    return _auth_response(current_user, settings, session_model=session_model)


@router.get("/sso/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
def sso_login() -> Response:
    settings = config.get_settings()
    if "sso" not in settings.auth_mode_sequence:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO is not enabled")
    location = sso.build_authorization_url(settings)
    response = Response(status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.headers["Location"] = location
    return response


@router.get("/sso/callback", response_model=AuthSessionResponse)
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
        user, claims = sso.exchange_code(settings, code=code, state=state, db=db)
    except SSOExchangeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ip_address, user_agent = _request_metadata(request)
    now_iso = datetime.now(timezone.utc).isoformat()
    user.last_login_at = now_iso

    session_model, raw_token = sessions.issue_session(
        db,
        user,
        settings=settings,
        ip_address=ip_address,
        user_agent=user_agent,
        commit=False,
    )

    login_success(
        db,
        user,
        mode="sso",
        source="api",
        payload={"ip": ip_address, "user_agent": user_agent, "subject": claims.get("sub")},
        commit=False,
    )
    db.commit()
    db.refresh(user)
    db.refresh(session_model)
    assert raw_token is not None
    _set_session_cookie(response, settings, raw_token)
    _set_request_context(
        request,
        user,
        mode="session",
        session_id=session_model.session_id,
        subject=claims.get("sub"),
    )
    return _auth_response(user, settings, session_model=session_model)
