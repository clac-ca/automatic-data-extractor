"""HTTP interface for authentication endpoints."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from ade_api.app.dependencies import get_auth_service
from ade_api.common.time import utc_now
from ade_api.core.auth.principal import PrincipalType
from ade_api.core.security.tokens import decode_token
from ade_api.settings import Settings, get_settings

from .schemas import (
    AuthLoginRequest,
    AuthProviderListResponse,
    AuthRefreshRequest,
    AuthSetupRequest,
    AuthSetupStatusResponse,
    SessionEnvelope,
    SessionSnapshot,
    SessionStatusResponse,
)
from .schemas import (
    SessionTokens as SessionTokensSchema,
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


# ---- Helpers ----


def _auth_error(status_code: int, *, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": code, "message": message})


def _serialize_tokens(tokens: SessionTokens) -> SessionTokensSchema:
    now = utc_now()
    access_expires_in = max(0, int((tokens.access_expires_at - now).total_seconds()))
    refresh_expires_in = (
        max(0, int((tokens.refresh_expires_at - now).total_seconds()))
        if tokens.refresh_expires_at
        else None
    )
    return SessionTokensSchema(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
        expires_in=access_expires_in,
        refresh_expires_in=refresh_expires_in,
    )


def _cookie_kwargs(settings: Settings, *, http_only: bool) -> dict[str, object]:
    public_url = (getattr(settings, "server_public_url", "") or "").lower()
    kwargs: dict[str, object] = {
        "httponly": http_only,
        "secure": public_url.startswith("https://"),
        "samesite": "lax",
        "path": settings.session_cookie_path or "/",
    }
    if settings.session_cookie_domain:
        kwargs["domain"] = settings.session_cookie_domain
    return kwargs


def _set_session_cookies(
    response: Response,
    tokens: SessionTokens,
    settings: Settings,
    *,
    csrf_token: str | None = None,
) -> None:
    access_cookie_kwargs = _cookie_kwargs(settings, http_only=True)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=tokens.access_token,
        max_age=max(1, int((tokens.access_expires_at - utc_now()).total_seconds())),
        expires=tokens.access_expires_at,
        **access_cookie_kwargs,
    )

    if tokens.refresh_token and tokens.refresh_expires_at:
        response.set_cookie(
            key=settings.session_refresh_cookie_name,
            value=tokens.refresh_token,
            max_age=max(1, int((tokens.refresh_expires_at - utc_now()).total_seconds())),
            expires=tokens.refresh_expires_at,
            **access_cookie_kwargs,
        )

    if csrf_token:
        csrf_kwargs = _cookie_kwargs(settings, http_only=False)
        response.set_cookie(
            key=settings.session_csrf_cookie_name,
            value=csrf_token,
            max_age=max(1, int((tokens.access_expires_at - utc_now()).total_seconds())),
            expires=tokens.access_expires_at,
            **csrf_kwargs,
        )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    base_kwargs = {
        "path": settings.session_cookie_path or "/",
        "domain": settings.session_cookie_domain,
    }
    response.delete_cookie(settings.session_cookie_name, **base_kwargs)
    response.delete_cookie(settings.session_refresh_cookie_name, **base_kwargs)
    response.delete_cookie(settings.session_csrf_cookie_name, **base_kwargs)


def _issue_session_envelope(
    *,
    tokens: SessionTokens,
    response: Response,
    settings: Settings,
) -> SessionEnvelope:
    csrf_token = secrets.token_urlsafe(32)
    _set_session_cookies(response, tokens, settings, csrf_token=csrf_token)
    return SessionEnvelope(session=_serialize_tokens(tokens), csrf_token=csrf_token)


def _extract_refresh_token(
    request: Request,
    payload: AuthRefreshRequest | None,
    settings: Settings,
) -> str:
    if payload and payload.refresh_token:
        return payload.refresh_token

    cookie_token = request.cookies.get(settings.session_refresh_cookie_name)
    if cookie_token:
        return cookie_token

    raise _auth_error(
        status.HTTP_400_BAD_REQUEST,
        code="refresh_token_required",
        message="Refresh token is required.",
    )


def _extract_access_token(request: Request, settings: Settings) -> str | None:
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()

    cookie_token = request.cookies.get(settings.session_cookie_name)
    if cookie_token:
        return cookie_token

    return None


def _decode_access_snapshot(token: str, settings: Settings) -> SessionSnapshot:
    try:
        payload = decode_token(
            token=token,
            secret=settings.jwt_secret_value,
            algorithms=[settings.jwt_algorithm],
        )
    except Exception as exc:
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            code="invalid_token",
            message="Invalid or expired access token.",
        ) from exc

    token_type = str(payload.get("typ") or "").lower()
    if token_type != "access":
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            code="invalid_token",
            message="Access token required.",
        )

    subject = str(payload.get("sub") or "").strip()
    if not subject:
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            code="invalid_token",
            message="Access token is missing subject.",
        )

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            code="invalid_token",
            message="Access token subject is invalid.",
        ) from exc

    principal_type_raw = str(payload.get("pt") or PrincipalType.USER.value).lower()
    principal_types = {pt.value for pt in PrincipalType}
    principal_type = (
        principal_type_raw
        if principal_type_raw in principal_types
        else PrincipalType.USER.value
    )

    exp = payload.get("exp")
    if exp is None:
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            code="invalid_token",
            message="Access token is missing expiry.",
        )
    expires_at = datetime.fromtimestamp(int(exp), tz=UTC)

    issued_at_val = payload.get("iat")
    issued_at = datetime.fromtimestamp(int(issued_at_val), tz=UTC) if issued_at_val else None

    return SessionSnapshot(
        user_id=user_id,
        principal_type=principal_type,  # type: ignore[arg-type]
        issued_at=issued_at,
        expires_at=expires_at,
    )


def _should_redirect_to_frontend(
    request: Request,
    response_mode: Literal["json", "redirect"] | None = None,
) -> bool:
    if response_mode == "json":
        return False
    if response_mode == "redirect":
        return True

    accept = (request.headers.get("accept") or "").lower()
    wants_json = "application/json" in accept or "+json" in accept
    return not wants_json


def _frontend_redirect_target(settings: Settings, state: str) -> str:
    base = (getattr(settings, "frontend_url", None) or settings.server_public_url).rstrip("/")
    return f"{base}/sso-complete?state={quote(state, safe='')}"


# ---- Routes ----


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
    response_model=SessionEnvelope,
    status_code=status.HTTP_201_CREATED,
    summary="Create the first administrator account and start a session",
)
async def complete_setup(
    payload: AuthSetupRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> SessionEnvelope:
    try:
        tokens = await service.complete_initial_setup(payload)
    except SetupAlreadyCompletedError as exc:
        raise _auth_error(
            status.HTTP_409_CONFLICT,
            code="setup_already_completed",
            message=str(exc),
        ) from exc

    return _issue_session_envelope(tokens=tokens, response=response, settings=settings)


@router.post(
    "/session",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Create a session via email/password",
)
async def create_session(
    payload: AuthLoginRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> SessionEnvelope:
    try:
        tokens = await service.login_with_password(
            email=str(payload.email),
            password=payload.password.get_secret_value(),
        )
    except InvalidCredentialsError as exc:
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message=str(exc),
        ) from exc
    except InactiveUserError as exc:
        raise _auth_error(
            status.HTTP_403_FORBIDDEN,
            code="inactive_user",
            message=str(exc),
        ) from exc
    except AccountLockedError as exc:
        raise _auth_error(
            status.HTTP_423_LOCKED,
            code="account_locked",
            message=str(exc),
        ) from exc

    return _issue_session_envelope(tokens=tokens, response=response, settings=settings)


@router.post(
    "/session/refresh",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Refresh an existing session using a refresh token",
)
async def refresh_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    response: Response,
    payload: Annotated[AuthRefreshRequest | None, Body()] = None,
) -> SessionEnvelope:
    refresh_token = _extract_refresh_token(request, payload, settings)
    try:
        tokens = await service.refresh_session(refresh_token=refresh_token)
    except RefreshTokenError as exc:
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            code="invalid_refresh_token",
            message=str(exc),
        ) from exc
    except AccountLockedError as exc:
        raise _auth_error(
            status.HTTP_423_LOCKED,
            code="account_locked",
            message=str(exc),
        ) from exc

    return _issue_session_envelope(tokens=tokens, response=response, settings=settings)


@router.get(
    "/session",
    response_model=SessionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the current session snapshot",
)
async def read_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionStatusResponse:
    token = _extract_access_token(request, settings)
    if not token:
        raise _auth_error(
            status.HTTP_401_UNAUTHORIZED,
            code="unauthenticated",
            message="No active session.",
        )

    snapshot = _decode_access_snapshot(token, settings)
    return SessionStatusResponse(session=snapshot)


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate the current session",
)
async def end_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    response: Response,
    payload: Annotated[AuthRefreshRequest | None, Body()] = None,
) -> Response:
    try:
        refresh_token = _extract_refresh_token(request, payload, settings)
    except HTTPException:
        refresh_token = None

    await service.logout(refresh_token=refresh_token)
    _clear_session_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


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
    try:
        redirect_url = await service.start_sso_login(provider=provider, return_to=next_path)
    except NotImplementedError:
        raise _auth_error(
            status.HTTP_404_NOT_FOUND,
            code="sso_not_configured",
            message="SSO login is not configured for this deployment.",
        ) from None

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/sso/{provider}/callback",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Handle the SSO callback and issue tokens",
    responses={
        status.HTTP_302_FOUND: {
            "description": (
                "Redirect to the frontend after establishing a browser session. "
                "Includes session cookies."
            )
        }
    },
)
async def finish_sso_login(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    provider: str,
    code: str | None = None,
    state: str | None = None,
    response_mode: Literal["json", "redirect"] | None = None,
) -> SessionEnvelope | RedirectResponse:
    if not code or not state:
        raise _auth_error(
            status.HTTP_400_BAD_REQUEST,
            code="invalid_sso_callback",
            message="Missing SSO authorization code or state.",
        )

    try:
        tokens = await service.complete_sso_login(provider=provider, code=code, state=state)
    except NotImplementedError:
        raise _auth_error(
            status.HTTP_404_NOT_FOUND,
            code="sso_not_configured",
            message="SSO login is not configured for this deployment.",
        ) from None

    if _should_redirect_to_frontend(request, response_mode=response_mode):
        redirect = RedirectResponse(
            url=_frontend_redirect_target(settings, state),
            status_code=status.HTTP_302_FOUND,
        )
        _set_session_cookies(redirect, tokens, settings, csrf_token=secrets.token_urlsafe(32))
        return redirect

    return _issue_session_envelope(tokens=tokens, response=response, settings=settings)
