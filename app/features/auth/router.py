"""Routes for authentication flows."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.core.schema import ErrorMessage

from ..users.dependencies import get_users_service
from ..users.models import User
from ..users.schemas import UserProfile
from ..users.service import UsersService
from .dependencies import bind_current_user, get_auth_service
from .schemas import (
    APIKeyIssueRequest,
    APIKeyIssueResponse,
    APIKeySummary,
    InitialSetupRequest,
    InitialSetupStatus,
    LoginRequest,
    SessionEnvelope,
)
from .security import access_control
from .service import SSO_STATE_COOKIE, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AdminAuthServiceDep = Annotated[
    AuthService,
    Depends(access_control(require_admin=True)),
]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
UserDep = Annotated[User, Depends(bind_current_user)]


@router.get(
    "/initial-setup",
    response_model=InitialSetupStatus,
    status_code=status.HTTP_200_OK,
    summary="Return whether initial admin setup is required",
    openapi_extra={"security": []},
)
async def read_initial_setup_status(
    service: AuthServiceDep,
) -> InitialSetupStatus:
    required = await service.initial_setup_required()
    return InitialSetupStatus(initial_setup_required=required)


@router.post(
    "/initial-setup",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Create the first administrator account",
    openapi_extra={"security": []},
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Initial setup already completed or email already in use.",
            "model": ErrorMessage,
        }
    },
)
async def perform_initial_setup(
    request: Request,
    response: Response,
    payload: InitialSetupRequest,
    service: AuthServiceDep,
) -> SessionEnvelope:
    user = await service.complete_initial_setup(
        email=payload.email,
        password=payload.password.get_secret_value(),
        display_name=payload.display_name,
    )
    tokens = await service.start_session(user=user)
    secure_cookie = service.is_secure_request(request)
    service.apply_session_cookies(response, tokens, secure=secure_cookie)
    profile = UserProfile.model_validate(user)
    return SessionEnvelope(
        user=profile,
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
    )


@router.post(
    "/login",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with email and password",
    openapi_extra={"security": []},
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid credentials provided.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "User account is inactive or service account credentials were supplied.",
            "model": ErrorMessage,
        },
    },
)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    service: AuthServiceDep,
) -> SessionEnvelope:
    """Authenticate with credentials and establish the session cookies."""

    user = await service.authenticate(
        email=payload.email,
        password=payload.password.get_secret_value(),
    )
    tokens = await service.start_session(user=user)
    secure_cookie = service.is_secure_request(request)
    service.apply_session_cookies(response, tokens, secure=secure_cookie)
    profile = UserProfile.model_validate(user)
    return SessionEnvelope(
        user=profile,
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
    )


@router.post(
    "/refresh",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Refresh the active browser session",
    openapi_extra={"security": []},
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Refresh token missing or invalid.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "CSRF validation failed for the refresh request.",
            "model": ErrorMessage,
        },
    },
)
async def refresh_session(
    request: Request,
    response: Response,
    service: AuthServiceDep,
) -> SessionEnvelope:
    """Rotate the session using the refresh cookie and re-issue cookies."""

    refresh_cookie = request.cookies.get(service.settings.session_refresh_cookie_name)
    if not refresh_cookie:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")
    try:
        payload = service.decode_token(refresh_cookie, expected_type="refresh")
    except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    service.enforce_csrf(request, payload)
    user = await service.resolve_user(payload)
    tokens = await service.refresh_session(payload=payload, user=user)
    secure_cookie = service.is_secure_request(request)
    service.apply_session_cookies(response, tokens, secure=secure_cookie)
    profile = UserProfile.model_validate(user)
    return SessionEnvelope(
        user=profile,
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate the active session",
    openapi_extra={"security": []},
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Session token is missing or invalid.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "CSRF validation failed for the logout request.",
            "model": ErrorMessage,
        },
    },
)
async def logout(
    request: Request,
    response: Response,
    service: AuthServiceDep,
) -> Response:
    """Remove authentication cookies and end the session."""

    session_cookie = request.cookies.get(service.settings.session_cookie_name)
    if session_cookie:
        try:
            payload = service.decode_token(session_cookie, expected_type="access")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session token",
            ) from exc
        service.enforce_csrf(request, payload)
    service.clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get(
    "/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    response_model_exclude_none=True,
    summary="Return the authenticated user profile",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to access the profile.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Service account credentials cannot access this endpoint.",
            "model": ErrorMessage,
        },
    },
)
async def who_am_i(
    _: UserDep,
    users_service: UsersServiceDep,
) -> UserProfile:
    """Return profile information for the active user."""

    profile = await users_service.get_profile()
    return profile


@router.post(
    "/api-keys",
    response_model=APIKeyIssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new API key for a user",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Email required or target user is inactive.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage API keys.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Administrator role required to issue API keys.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Specified user could not be found.",
            "model": ErrorMessage,
        },
    },
)
async def create_api_key(
    payload: APIKeyIssueRequest,
    _: UserDep,
    service: AdminAuthServiceDep,
) -> APIKeyIssueResponse:
    if payload.user_id is not None:
        result = await service.issue_api_key_for_user_id(
            user_id=payload.user_id,
            expires_in_days=payload.expires_in_days,
        )
    else:
        email = payload.email
        if email is None:  # pragma: no cover - validated upstream
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Email required",
            )
        result = await service.issue_api_key_for_email(
            email=email,
            expires_in_days=payload.expires_in_days,
        )

    return APIKeyIssueResponse(
        api_key=result.raw_key,
        principal_type=result.principal_type,
        principal_id=result.user.id,
        principal_label=result.principal_label,
        expires_at=result.api_key.expires_at,
    )


@router.get(
    "/api-keys",
    response_model=list[APIKeySummary],
    status_code=status.HTTP_200_OK,
    summary="List issued API keys",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list API keys.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Administrator role required to list API keys.",
            "model": ErrorMessage,
        },
    },
)
async def list_api_keys(
    _: UserDep,
    service: AdminAuthServiceDep,
) -> list[APIKeySummary]:
    records = await service.list_api_keys()
    return [
        APIKeySummary(
            api_key_id=record.id,
            principal_type=(
                "service_account"
                if record.user is not None and record.user.is_service_account
                else "user"
            ),
            principal_id=record.user_id,
            principal_label=(
                record.user.label
                if record.user is not None
                else ""
            ),
            token_prefix=record.token_prefix,
            created_at=record.created_at,
            expires_at=record.expires_at,
            last_seen_at=record.last_seen_at,
            last_seen_ip=record.last_seen_ip,
            last_seen_user_agent=record.last_seen_user_agent,
        )
        for record in records
    ]


@router.delete(
    "/api-keys/{api_key_id}",
    summary="Revoke an API key",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to revoke API keys.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Administrator role required to revoke API keys.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "API key not found.",
            "model": ErrorMessage,
        },
    },
)
async def revoke_api_key(
    api_key_id: str,
    _: UserDep,
    service: AdminAuthServiceDep,
) -> Response:
    await service.revoke_api_key(api_key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/sso/login",
    status_code=status.HTTP_302_FOUND,
    summary="Initiate the SSO login flow",
    openapi_extra={"security": []},
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "SSO login is not configured for this deployment.",
            "model": ErrorMessage,
        }
    },
)
async def start_sso_login(
    request: Request,
    service: AuthServiceDep,
) -> RedirectResponse:
    challenge = await service.prepare_sso_login()
    redirect = RedirectResponse(challenge.redirect_url, status_code=status.HTTP_302_FOUND)
    secure_cookie = service.is_secure_request(request)
    redirect.set_cookie(
        key=SSO_STATE_COOKIE,
        value=challenge.state_token,
        httponly=True,
        secure=secure_cookie,
        max_age=challenge.expires_in,
        samesite="lax",
        path="/auth/sso",
    )
    return redirect


@router.get(
    "/sso/callback",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Handle the SSO callback and establish a session",
    openapi_extra={"security": []},
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Callback parameters invalid or identity provider response rejected.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "User account associated with the SSO identity is disabled.",
            "model": ErrorMessage,
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "ADE could not reach the identity provider during the SSO exchange.",
            "model": ErrorMessage,
        },
    },
)
async def finish_sso_login(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    code: str | None = None,
    state: str | None = None,
) -> SessionEnvelope:
    if not code or not state:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code or state",
        )

    state_cookie = request.cookies.get(SSO_STATE_COOKIE)
    if not state_cookie:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Missing SSO state cookie",
        )

    try:
        user = await service.complete_sso_login(
            code=code,
            state=state,
            state_token=state_cookie,
        )
    finally:
        response.delete_cookie(SSO_STATE_COOKIE, path="/auth/sso")

    tokens = await service.start_session(user=user)
    secure_cookie = service.is_secure_request(request)
    service.apply_session_cookies(response, tokens, secure=secure_cookie)
    profile = UserProfile.model_validate(user)
    return SessionEnvelope(
        user=profile,
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
    )


__all__ = ["router"]
