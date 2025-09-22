"""Authentication API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import config
from ..auth.email import EmailValidationError, normalize_email
from ..db import get_db
from ..models import User
from ..schemas import (
    APIKeyIssueRequest,
    APIKeyIssueResponse,
    APIKeySummary,
    TokenResponse,
    UserProfile,
)
from ..services import EventRecord, auth as auth_service, record_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse, openapi_extra={"security": []})
def issue_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    settings: config.Settings = Depends(config.get_settings),
) -> TokenResponse:
    """Exchange email/password credentials for a bearer token."""

    if settings.auth_disabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Authentication is disabled; tokens are unnecessary",
        )

    user = auth_service.authenticate_user(
        db,
        email=form_data.username,
        password=form_data.password,
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = auth_service.create_access_token(user, settings)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserProfile)
async def who_am_i(current_user: User = Depends(auth_service.get_current_user)) -> UserProfile:
    """Return the profile for the currently authenticated user."""

    return UserProfile.model_validate(current_user)


@router.get("/sso/login", openapi_extra={"security": []})
async def start_sso_login(
    request: Request,
    settings: config.Settings = Depends(config.get_settings),
) -> RedirectResponse:
    """Initiate an authorization-code flow with PKCE."""

    challenge = await auth_service.prepare_sso_login(settings)
    redirect = RedirectResponse(challenge.redirect_url, status_code=status.HTTP_302_FOUND)
    secure_cookie = request.url.scheme == "https"
    redirect.set_cookie(
        key=auth_service.SSO_STATE_COOKIE,
        value=challenge.state_token,
        httponly=True,
        secure=secure_cookie,
        max_age=challenge.expires_in,
        samesite="lax",
        path="/auth/sso",
    )
    return redirect


@router.get("/sso/callback", response_model=TokenResponse, openapi_extra={"security": []})
async def finish_sso_login(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    settings: config.Settings = Depends(config.get_settings),
) -> TokenResponse:
    """Complete the SSO flow and issue an ADE access token."""

    if not settings.sso_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO not configured")
    if not code or not state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing authorization code or state")

    state_cookie = request.cookies.get(auth_service.SSO_STATE_COOKIE)
    if not state_cookie:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing SSO state cookie")

    provider = settings.sso_issuer or ""
    email: str | None = None
    subject: str | None = None
    user: User | None = None

    try:
        try:
            stored_state = auth_service.decode_sso_state(state_cookie, settings)
        finally:
            response.delete_cookie(auth_service.SSO_STATE_COOKIE, path="/auth/sso")

        if stored_state.state != state:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="State mismatch")

        token_response = await auth_service.exchange_authorization_code(
            settings,
            code=code,
            code_verifier=stored_state.code_verifier,
        )
        metadata = await auth_service.get_oidc_metadata(settings)

        id_token = token_response.get("id_token")
        access_token = token_response.get("access_token")
        token_type = str(token_response.get("token_type", "")).lower()
        if not id_token or not access_token or token_type != "bearer":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid token response from identity provider")

        id_claims = auth_service.verify_jwt_via_jwks(
            id_token,
            metadata.jwks_uri,
            audience=settings.sso_client_id,
            issuer=settings.sso_issuer,
            nonce=stored_state.nonce,
        )

        if settings.sso_resource_audience:
            auth_service.verify_jwt_via_jwks(
                access_token,
                metadata.jwks_uri,
                audience=settings.sso_resource_audience,
                issuer=settings.sso_issuer,
            )

        email = str(id_claims.get("email") or "")
        subject = str(id_claims.get("sub") or "")
        email_verified = bool(id_claims.get("email_verified"))
        if not email or not subject:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Identity provider response missing required claims")

        user = auth_service.resolve_sso_user(
            db,
            provider=settings.sso_issuer,
            subject=subject,
            email=email,
            email_verified=email_verified,
        )
    except HTTPException as exc:
        record_event(
            db,
            EventRecord(
                event_type="auth.sso.login.failed",
                entity_type="auth",
                entity_id="sso",
                payload={
                    "provider": provider,
                    "email": email or None,
                    "subject": subject or None,
                    "status_code": exc.status_code,
                    "detail": str(exc.detail),
                },
                source="api",
            ),
            commit=True,
        )
        raise

    if user is None:  # pragma: no cover - defensive guard
        raise RuntimeError("SSO user resolution failed")
    actor = auth_service.event_actor_from_user(user)
    record_event(
        db,
        EventRecord(
            event_type="auth.sso.login.succeeded",
            entity_type="user",
            entity_id=user.user_id,
            payload={
                "provider": provider,
                "email": user.email,
                "subject": user.sso_subject or subject,
            },
            actor_type=actor["actor_type"],
            actor_id=actor["actor_id"],
            actor_label=actor["actor_label"],
            source="api",
        ),
        commit=False,
    )

    token = auth_service.create_access_token(user, settings)
    return TokenResponse(access_token=token)


@router.post("/api-keys", response_model=APIKeyIssueResponse)
def create_api_key(
    payload: APIKeyIssueRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(auth_service.require_admin),
) -> APIKeyIssueResponse:
    """Issue a new API key for the requested user."""

    try:
        normalised = normalize_email(payload.email)
    except EmailValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    target = (
        db.query(User)
        .filter(User.email_canonical == normalised.canonical)
        .one_or_none()
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if not target.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Target user is inactive")

    expires_at_dt = None
    if payload.expires_in_days is not None:
        expires_at_dt = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    actor = auth_service.event_actor_from_user(current_admin)
    raw_key, api_key = auth_service.issue_api_key(
        db,
        target,
        expires_at=expires_at_dt,
        actor=actor,
        source="api",
    )
    return APIKeyIssueResponse(api_key=raw_key, expires_at=api_key.expires_at)


@router.get("/api-keys", response_model=list[APIKeySummary])
def list_api_keys(
    db: Session = Depends(get_db),
    _: User = Depends(auth_service.require_admin),
) -> list[APIKeySummary]:
    """Return issued API keys with owner and last-seen metadata."""

    keys = auth_service.list_api_keys(db)
    return [APIKeySummary.model_validate(key) for key in keys]


@router.delete(
    "/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_api_key(
    api_key_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(auth_service.require_admin),
) -> Response:
    """Revoke an API key immediately."""

    actor = auth_service.event_actor_from_user(current_admin)
    try:
        auth_service.revoke_api_key(
            db,
            api_key_id,
            actor=actor,
            source="api",
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
