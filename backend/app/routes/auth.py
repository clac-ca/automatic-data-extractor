"""Authentication API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from .. import config
from ..services import EventRecord, auth as auth_service, record_event
from ..db import get_db
from ..models import User, UserSession
from ..schemas import AuthSessionResponse, SessionSummary, UserProfile

logger = logging.getLogger(__name__)

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
def login_basic(
    request: Request,
    response: Response,
    settings: config.Settings = Depends(config.get_settings),
    user: User = Depends(auth_service.require_basic_auth_user),
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
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
    return _auth_response(user, settings, session_model=session_model)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    openapi_extra={"security": []},
)
def logout(
    request: Request,
    response: Response,
    settings: config.Settings = Depends(config.get_settings),
    identity: auth_service.AuthenticatedIdentity = Depends(
        auth_service.get_authenticated_identity
    ),
    db: Session = Depends(get_db),
) -> Response:
    ip_address, user_agent = _request_metadata(request)

    session_model = identity.session
    if session_model is not None:
        auth_service.revoke_session(db, session_model, commit=False)
        record_event(
            db,
            EventRecord(
                event_type="user.logout",
                entity_type="user",
                entity_id=identity.user.user_id,
                actor_type="user",
                actor_id=identity.user.user_id,
                actor_label=identity.user.email,
                source="api",
                payload={
                    "session_id": session_model.session_id,
                    "ip": ip_address,
                    "user_agent": user_agent,
                },
            ),
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
    response: Response,
    session_token: str = Depends(auth_service.require_session_cookie),
    settings: config.Settings = Depends(config.get_settings),
    identity: auth_service.AuthenticatedIdentity = Depends(
        auth_service.get_authenticated_identity
    ),
    db: Session = Depends(get_db),
) -> AuthSessionResponse:

    session_model = identity.session
    if session_model is None:
        _clear_session_cookie(response, settings)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Session expired")

    record_event(
        db,
        EventRecord(
            event_type="user.session.refreshed",
            entity_type="user",
            entity_id=identity.user.user_id,
            actor_type="user",
            actor_id=identity.user.user_id,
            actor_label=identity.user.email,
            source="api",
            payload={"session_id": session_model.session_id},
        ),
        commit=False,
    )
    db.commit()
    _set_session_cookie(response, settings, session_token)
    return _auth_response(identity.user, settings, session_model=session_model)


@router.get(
    "/me",
    response_model=AuthSessionResponse,
    openapi_extra={"security": []},
)
def current_user_profile(
    settings: config.Settings = Depends(config.get_settings),
    identity: auth_service.AuthenticatedIdentity = Depends(
        auth_service.get_authenticated_identity
    ),
) -> AuthSessionResponse:
    return _auth_response(identity.user, settings, session_model=identity.session)


@router.get(
    "/sso/login",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    openapi_extra={"security": []},
)
def sso_login(
    settings: config.Settings = Depends(config.get_settings),
) -> Response:
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
    settings: config.Settings = Depends(config.get_settings),
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
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
    return _auth_response(user, settings, session_model=session_model)
