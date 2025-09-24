"""Routes for authentication flows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
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
    TokenResponse,
)
from .security import access_control
from .service import SSO_STATE_COOKIE, AuthService


async def _parse_api_key_issue_request(request: Request) -> APIKeyIssueRequest:
    payload = await request.json()
    return APIKeyIssueRequest.model_validate(payload)


router = APIRouter(prefix="/auth", tags=["auth"])


@cbv(router)
class AuthRoutes:
    session: AsyncSession = Depends(get_session)  # noqa: B008
    service: AuthService = Depends(get_auth_service)  # noqa: B008

    @router.post(
        "/token",
        response_model=TokenResponse,
        status_code=status.HTTP_200_OK,
        summary="Exchange credentials for an access token",
        openapi_extra={"security": []},
    )
    async def issue_token(
        self,
        form: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
    ) -> TokenResponse:
        """Return a JWT for the supplied email/password combination."""

        user = await self.service.authenticate(email=form.username, password=form.password)
        token = await self.service.issue_token(user)
        return TokenResponse(access_token=token)

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
        payload: APIKeyIssueRequest = Depends(_parse_api_key_issue_request),  # noqa: B008
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
        secure_cookie = request.url.scheme == "https"
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
        response_model=TokenResponse,
        status_code=status.HTTP_200_OK,
        summary="Handle the SSO callback and issue a token",
        openapi_extra={"security": []},
    )
    async def finish_sso_login(
        self,
        request: Request,
        response: Response,
        code: str | None = None,
        state: str | None = None,
    ) -> TokenResponse:
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

        token = await self.service.issue_token(user)
        return TokenResponse(access_token=token)


__all__ = ["router"]
