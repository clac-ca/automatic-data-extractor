"""Routes for authentication flows."""

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..users.dependencies import get_users_service
from ..users.models import User
from ..users.schemas import UserProfile
from ..users.service import UsersService
from .dependencies import bind_current_user, get_auth_service
from .schemas import (
    APIKeyIssueRequest,
    APIKeyIssueResponse,
    APIKeySummary,
    LoginRequest,
    SessionEnvelope,
)
from .security import access_control
from .service import SSO_STATE_COOKIE, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
@cbv(router)
class AuthRoutes:
    session: AsyncSession = Depends(get_session)  # noqa: B008
    service: AuthService = Depends(get_auth_service)  # noqa: B008

    @router.post(
        "/login",
        response_model=SessionEnvelope,
        status_code=status.HTTP_200_OK,
        summary="Authenticate with email and password",
        openapi_extra={"security": []},
    )
    async def login(
        self,
        request: Request,
        response: Response,
        payload: LoginRequest,
    ) -> SessionEnvelope:
        """Authenticate with credentials and establish the session cookies."""

        user = await self.service.authenticate(
            email=payload.email,
            password=payload.password.get_secret_value(),
        )
        tokens = await self.service.start_session(user=user)
        secure_cookie = self.service.is_secure_request(request)
        self.service.apply_session_cookies(response, tokens, secure=secure_cookie)
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
    )
    async def refresh_session(
        self,
        request: Request,
        response: Response,
    ) -> SessionEnvelope:
        """Rotate the session using the refresh cookie and re-issue cookies."""

        refresh_cookie = request.cookies.get(
            self.service.settings.session_refresh_cookie_name
        )
        if not refresh_cookie:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")
        try:
            payload = self.service.decode_token(refresh_cookie, expected_type="refresh")
        except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

        self.service.enforce_csrf(request, payload)
        user = await self.service.resolve_user(payload)
        tokens = await self.service.refresh_session(payload=payload, user=user)
        secure_cookie = self.service.is_secure_request(request)
        self.service.apply_session_cookies(response, tokens, secure=secure_cookie)
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
    )
    async def logout(self, request: Request, response: Response) -> Response:
        """Remove authentication cookies and end the session."""

        session_cookie = request.cookies.get(self.service.settings.session_cookie_name)
        if session_cookie:
            try:
                payload = self.service.decode_token(session_cookie, expected_type="access")
            except jwt.PyJWTError as exc:  # pragma: no cover - dependent on jwt internals
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session token") from exc
            self.service.enforce_csrf(request, payload)
        self.service.clear_session_cookies(response)
        response.status_code = status.HTTP_204_NO_CONTENT
        return response

    @router.get(
        "/me",
        response_model=UserProfile,
        status_code=status.HTTP_200_OK,
        response_model_exclude_none=True,
        summary="Return the authenticated user profile",
    )
    async def who_am_i(
        self,
        _current_user: User = Depends(bind_current_user),  # noqa: B008
        users_service: UsersService = Depends(get_users_service),  # noqa: B008
    ) -> UserProfile:
        """Return profile information for the active user."""

        profile = await users_service.get_profile()
        return profile

    @router.post(
        "/api-keys",
        response_model=APIKeyIssueResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Issue a new API key for a user",
    )
    @access_control(require_admin=True)
    async def create_api_key(
        self,
        payload: APIKeyIssueRequest,
        _current_user: User = Depends(bind_current_user),  # noqa: B008
    ) -> APIKeyIssueResponse:
        if payload.user_id is not None:
            result = await self.service.issue_api_key_for_user_id(
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
            result = await self.service.issue_api_key_for_email(
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
    )
    @access_control(require_admin=True)
    async def list_api_keys(
        self,
        _: User = Depends(bind_current_user),  # noqa: B008
    ) -> list[APIKeySummary]:
        records = await self.service.list_api_keys()
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
    )
    @access_control(require_admin=True)
    async def revoke_api_key(
        self,
        api_key_id: str,
        _: User = Depends(bind_current_user),  # noqa: B008
    ) -> Response:
        await self.service.revoke_api_key(api_key_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get(
        "/sso/login",
        status_code=status.HTTP_302_FOUND,
        summary="Initiate the SSO login flow",
        openapi_extra={"security": []},
    )
    async def start_sso_login(self, request: Request) -> RedirectResponse:
        challenge = await self.service.prepare_sso_login()
        redirect = RedirectResponse(challenge.redirect_url, status_code=status.HTTP_302_FOUND)
        secure_cookie = self.service.is_secure_request(request)
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
    )
    async def finish_sso_login(
        self,
        request: Request,
        response: Response,
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
            user = await self.service.complete_sso_login(
                code=code,
                state=state,
                state_token=state_cookie,
            )
        finally:
            response.delete_cookie(SSO_STATE_COOKIE, path="/auth/sso")

        tokens = await self.service.start_session(user=user)
        secure_cookie = self.service.is_secure_request(request)
        self.service.apply_session_cookies(response, tokens, secure=secure_cookie)
        profile = UserProfile.model_validate(user)
        return SessionEnvelope(
            user=profile,
            expires_at=tokens.access_expires_at,
            refresh_expires_at=tokens.refresh_expires_at,
        )


__all__ = ["router"]
