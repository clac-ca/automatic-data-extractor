"""HTTP interface for authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from ade_api.app.dependencies import get_auth_service
from ade_api.common.time import utc_now
from ade_api.settings import Settings, get_settings

from .schemas import (
    AuthLoginRequest,
    AuthProviderListResponse,
    AuthRefreshRequest,
    AuthSetupRequest,
    AuthSetupStatusResponse,
    AuthTokensResponse,
)
from .service import (
    AccountLockedError,
    AuthService,
    InactiveUserError,
    InvalidCredentialsError,
    RefreshTokenError,
    SessionTokens,
    SetupAlreadyCompletedError,
)

router = APIRouter(tags=["auth"])


def _session_tokens_to_response(tokens: SessionTokens) -> AuthTokensResponse:
    """Convert internal SessionTokens to API response model."""

    now = utc_now()
    access_expires_in = max(0, int((tokens.access_expires_at - now).total_seconds()))
    refresh_expires_in = max(0, int((tokens.refresh_expires_at - now).total_seconds()))
    return AuthTokensResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=access_expires_in,
        refresh_expires_in=refresh_expires_in,
    )


def _extract_refresh_token(
    request: Request,
    payload: AuthRefreshRequest | None,
    settings: Settings,
) -> str:
    """Resolve refresh token from body or cookie, preferring the body for API clients."""

    if payload and payload.refresh_token:
        return payload.refresh_token

    cookie_name = settings.session_refresh_cookie_name
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        return cookie_token

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Refresh token is required.",
    )


@router.get(
    "/providers",
    response_model=AuthProviderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List configured authentication providers",
)
async def list_auth_providers(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthProviderListResponse:
    return service.list_auth_providers()


@router.get(
    "/setup",
    response_model=AuthSetupStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Return whether initial administrator setup is required",
)
async def read_setup_status(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSetupStatusResponse:
    return await service.get_setup_status()


@router.post(
    "/setup",
    response_model=AuthTokensResponse,
    status_code=status.HTTP_200_OK,
    summary="Create the first administrator account",
)
async def complete_setup(
    payload: AuthSetupRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthTokensResponse:
    try:
        tokens = await service.complete_initial_setup(payload)
    except SetupAlreadyCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _session_tokens_to_response(tokens)


@router.post(
    "/session",
    response_model=AuthTokensResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a session via email/password and issue tokens",
)
async def create_session(
    payload: AuthLoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthTokensResponse:
    try:
        tokens = await service.login_with_password(
            email=str(payload.email),
            password=payload.password.get_secret_value(),
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(exc),
        ) from exc

    return _session_tokens_to_response(tokens)


@router.post(
    "/session/refresh",
    response_model=AuthTokensResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh an existing session using a refresh token",
)
async def refresh_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    payload: Annotated[AuthRefreshRequest | None, Body()] = None,
) -> AuthTokensResponse:
    refresh_token = _extract_refresh_token(request, payload, settings)
    try:
        tokens = await service.refresh_session(refresh_token=refresh_token)
    except RefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(exc),
        ) from exc

    return _session_tokens_to_response(tokens)


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate the current session",
)
async def end_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    payload: Annotated[AuthRefreshRequest | None, Body()] = None,
) -> Response:
    try:
        refresh_token = _extract_refresh_token(request, payload, settings)
    except HTTPException:
        refresh_token = None

    await service.logout(refresh_token=refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/sso/{provider}/authorize",
    status_code=status.HTTP_302_FOUND,
    summary="Initiate the SSO login flow",
)
async def start_sso_login(
    service: Annotated[AuthService, Depends(get_auth_service)],
    provider: str,
    next_path: str | None = None,
) -> RedirectResponse:
    """Initiate SSO / OIDC login."""

    try:
        redirect_url = await service.start_sso_login(provider=provider, return_to=next_path)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO login is not configured for this deployment.",
        ) from None

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/sso/{provider}/callback",
    response_model=AuthTokensResponse,
    status_code=status.HTTP_200_OK,
    summary="Handle the SSO callback and issue tokens",
)
async def finish_sso_login(
    service: Annotated[AuthService, Depends(get_auth_service)],
    provider: str,
    code: str | None = None,
    state: str | None = None,
) -> AuthTokensResponse:
    """Complete the SSO login flow."""

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing SSO authorization code or state.",
        )

    try:
        tokens = await service.complete_sso_login(provider=provider, code=code, state=state)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO login is not configured for this deployment.",
        ) from None

    return _session_tokens_to_response(tokens)
