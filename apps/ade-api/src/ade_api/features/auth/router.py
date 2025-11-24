"""Routes for authentication flows."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import jwt
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    Security,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.settings import Settings, get_settings
from ade_api.shared.db.session import get_session
from ade_api.shared.dependency import (
    get_current_identity,
    require_authenticated,
    require_csrf,
    require_global,
)
from ade_api.shared.pagination import PageParams

from ..users.models import User
from ..users.schemas import UserProfile
from ..users.service import UsersService
from .models import APIKey
from .schemas import (
    APIKeyIssueRequest,
    APIKeyIssueResponse,
    APIKeyPage,
    APIKeySummary,
    AuthProvider,
    LoginRequest,
    ProviderDiscoveryResponse,
    SessionEnvelope,
    SetupRequest,
    SetupStatus,
)
from .service import (
    SSO_STATE_COOKIE,
    AuthenticatedIdentity,
    AuthService,
)

router = APIRouter(prefix="/auth", tags=["auth"])
setup_router = APIRouter(prefix="/setup", tags=["setup"])


def _serialize_api_key(record: APIKey) -> APIKeySummary:
    principal_type = (
        "service_account"
        if record.user is not None and record.user.is_service_account
        else "user"
    )
    principal_label = (
        record.user.label if record.user is not None else record.label or ""
    )
    return APIKeySummary(
        id=record.id,
        principal_type=principal_type,
        principal_id=record.user_id,
        principal_label=principal_label,
        token_prefix=record.token_prefix,
        label=record.label,
        created_at=record.created_at,
        expires_at=record.expires_at,
        last_seen_at=record.last_seen_at,
        last_seen_ip=record.last_seen_ip,
        last_seen_user_agent=record.last_seen_user_agent,
        revoked_at=record.revoked_at,
    )


@router.get(
    "/providers",
    response_model=ProviderDiscoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="List configured authentication providers",
    openapi_extra={"security": []},
)
async def list_auth_providers(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProviderDiscoveryResponse:
    service = AuthService(session=session, settings=settings)
    discovery = service.get_provider_discovery()
    providers = [
        AuthProvider(
            id=provider.id,
            label=provider.label,
            start_url=provider.start_url,
            icon_url=provider.icon_url,
        )
        for provider in discovery.providers
    ]
    return ProviderDiscoveryResponse(providers=providers, force_sso=discovery.force_sso)


@setup_router.get(
    "/status",
    response_model=SetupStatus,
    status_code=status.HTTP_200_OK,
    summary="Return whether initial administrator setup is required",
    openapi_extra={"security": []},
)
async def read_setup_status(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SetupStatus:
    if settings.auth_disabled:
        return SetupStatus(
            requires_setup=False,
            completed_at=None,
            force_sso=settings.auth_force_sso,
        )
    service = AuthService(session=session, settings=settings)
    requires_setup, completed_at = await service.get_initial_setup_status()
    return SetupStatus(
        requires_setup=requires_setup,
        completed_at=completed_at,
        force_sso=settings.auth_force_sso,
    )


@setup_router.post(
    "",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Create the first administrator account",
    openapi_extra={"security": []},
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Initial setup already completed or email already in use."
        }
    },
)
async def complete_setup(
    request: Request,
    response: Response,
    payload: SetupRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionEnvelope:
    if settings.auth_disabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Interactive setup is disabled because ADE_AUTH_DISABLED is enabled.",
        )
    service = AuthService(session=session, settings=settings)
    user = await service.complete_initial_setup(
        email=payload.email,
        password=payload.password.get_secret_value(),
        display_name=payload.display_name,
    )
    tokens = await service.start_session(user=user)
    secure_cookie = service.is_secure_request(request)
    service.apply_session_cookies(response, tokens, secure=secure_cookie)
    user_profiles = UsersService(session=session)
    profile = await user_profiles.get_profile(user=user)
    return SessionEnvelope(
        user=profile,
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
    )


@router.post(
    "/session",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Create a browser session with email and password",
    openapi_extra={"security": []},
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid credentials provided."
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "User account is inactive or locked."
        },
    },
)
async def create_session(
    request: Request,
    response: Response,
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionEnvelope:
    """Authenticate with credentials and establish the session cookies."""

    service = AuthService(session=session, settings=settings)
    user = await service.authenticate(
        email=payload.email,
        password=payload.password.get_secret_value(),
    )
    tokens = await service.start_session(user=user)
    secure_cookie = service.is_secure_request(request)
    service.apply_session_cookies(response, tokens, secure=secure_cookie)
    user_profiles = UsersService(session=session)
    profile = await user_profiles.get_profile(user=user)
    return SessionEnvelope(
        user=profile,
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
    )


@router.get(
    "/session",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Return the active session profile",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to access the session profile.",
        }
    },
    dependencies=[Security(require_authenticated)],
)
async def read_session(
    request: Request,
    principal: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionEnvelope:
    service = AuthService(session=session, settings=settings)
    expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None

    if principal.credentials == "session_cookie":
        access_payload, refresh_payload = service.extract_session_payloads(
            request, include_refresh=False
        )
        expires_at = access_payload.expires_at
        if refresh_payload is not None:
            refresh_expires_at = refresh_payload.expires_at
    elif principal.credentials == "bearer_token":
        auth_header = request.headers.get("authorization")
        token_value: str | None = None
        if auth_header:
            scheme, _, candidate = auth_header.partition(" ")
            if scheme.lower() == "bearer":
                token_value = candidate.strip() or None
        if not token_value:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session token missing")
        try:
            payload = service.decode_token(token_value, expected_type="access")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session token",
            ) from exc
        expires_at = payload.expires_at

    user_profiles = UsersService(session=session)
    profile = await user_profiles.get_profile(user=principal.user)
    return SessionEnvelope(
        user=profile,
        expires_at=expires_at,
        refresh_expires_at=refresh_expires_at,
    )


@router.post(
    "/session/refresh",
    response_model=SessionEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Refresh the active browser session",
    openapi_extra={"security": []},
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Refresh token missing or invalid.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "CSRF validation failed for the refresh request.",
        },
    },
)
async def refresh_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionEnvelope:
    """Rotate the session using the refresh cookie and re-issue cookies."""

    service = AuthService(session=session, settings=settings)
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
    user_profiles = UsersService(session=session)
    profile = await user_profiles.get_profile(user=user)
    return SessionEnvelope(
        user=profile,
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
    )


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Terminate the active session",
    openapi_extra={"security": []},
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Session token is missing or invalid.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "CSRF validation failed for the logout request.",
        },
    },
    dependencies=[Security(require_authenticated), Security(require_csrf)],
)
async def delete_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Remove authentication cookies and end the session."""

    service = AuthService(session=session, settings=settings)
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
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Service account credentials cannot access this endpoint.",
        },
    },
)
async def read_me(
    current_user: Annotated[User, Security(require_authenticated)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserProfile:
    """Return profile information for the active user."""

    service = UsersService(session=session)
    profile = await service.get_profile(user=current_user)
    return profile


@router.post(
    "/api-keys",
    response_model=APIKeyIssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new API key for a user",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Email required or target user is inactive.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage API keys.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Administrator role required to issue API keys.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Specified user could not be found.",
        },
    },
    dependencies=[Security(require_csrf)],
)
async def create_api_key(
    payload: APIKeyIssueRequest,
    _admin: Annotated[
        User,
        Security(require_global("System.Settings.ReadWrite")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> APIKeyIssueResponse:
    service = AuthService(session=session, settings=settings)
    if payload.user_id is not None:
        result = await service.issue_api_key_for_user_id(
            user_id=payload.user_id,
            expires_in_days=payload.expires_in_days,
            label=payload.label,
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
            label=payload.label,
        )

    return APIKeyIssueResponse(
        api_key=result.raw_key,
        principal_type=result.principal_type,
        principal_id=result.user.id,
        principal_label=result.principal_label,
        expires_at=result.api_key.expires_at,
        label=result.api_key.label,
    )


@router.get(
    "/api-keys",
    response_model=APIKeyPage,
    status_code=status.HTTP_200_OK,
    summary="List issued API keys",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list API keys.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Administrator role required to list API keys.",
        },
    },
)
async def list_api_keys(
    _admin: Annotated[
        User,
        Security(require_global("System.Settings.ReadWrite")),
    ],
    page: Annotated[PageParams, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_revoked: Annotated[
        bool,
        Query(
            description="Include revoked API keys in the response.",
        ),
    ] = False,
) -> APIKeyPage:
    service = AuthService(session=session, settings=settings)
    api_key_page = await service.paginate_api_keys(
        include_revoked=include_revoked,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    summaries = [_serialize_api_key(record) for record in api_key_page.items]
    return APIKeyPage(
        items=summaries,
        page=api_key_page.page,
        page_size=api_key_page.page_size,
        has_next=api_key_page.has_next,
        has_previous=api_key_page.has_previous,
        total=api_key_page.total,
    )


@router.delete(
    "/api-keys/{api_key_id}",
    summary="Revoke an API key",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to revoke API keys.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Administrator role required to revoke API keys.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "API key not found.",
        },
    },
    dependencies=[Security(require_csrf)],
)
async def revoke_api_key(
    api_key_id: str,
    _admin: Annotated[
        User,
        Security(require_global("System.Settings.ReadWrite")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    service = AuthService(session=session, settings=settings)
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
        }
    },
)
async def start_sso_login(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    next_path: Annotated[str | None, Query(alias="next")] = None,
) -> RedirectResponse:
    service = AuthService(session=session, settings=settings)
    challenge = await service.prepare_sso_login(return_to=next_path)
    redirect = RedirectResponse(challenge.redirect_url, status_code=status.HTTP_302_FOUND)
    secure_cookie = service.is_secure_request(request)
    cookie_path = request.url.path.rsplit("/", 1)[0]
    redirect.set_cookie(
        key=SSO_STATE_COOKIE,
        value=challenge.state_token,
        httponly=True,
        secure=secure_cookie,
        max_age=challenge.expires_in,
        samesite="lax",
        path=cookie_path,
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
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "User account associated with the SSO identity is disabled.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "ADE could not reach the identity provider during the SSO exchange.",
        },
    },
)
async def finish_sso_login(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
) -> SessionEnvelope:
    service = AuthService(session=session, settings=settings)
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
        result = await service.complete_sso_login(
            code=code,
            state=state,
            state_token=state_cookie,
        )
    finally:
        cookie_path = request.url.path.rsplit("/", 1)[0]
        response.delete_cookie(SSO_STATE_COOKIE, path=cookie_path)

    tokens = await service.start_session(user=result.user)
    secure_cookie = service.is_secure_request(request)
    service.apply_session_cookies(response, tokens, secure=secure_cookie)
    user_profiles = UsersService(session=session)
    profile = await user_profiles.get_profile(user=result.user)
    return SessionEnvelope(
        user=profile,
        expires_at=tokens.access_expires_at,
        refresh_expires_at=tokens.refresh_expires_at,
        return_to=result.return_to,
    )


__all__ = ["router", "setup_router"]
