"""Routes for authentication flows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
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
    TokenResponse,
)
from .security import access_control
from .service import APIKeyPrincipalType, AuthService, SSO_STATE_COOKIE


async def _parse_api_key_issue_request(request: Request) -> APIKeyIssueRequest:
    payload = await request.json()
    return APIKeyIssueRequest.model_validate(payload)


router = APIRouter(prefix="/auth", tags=["auth"])


@cbv(router)
class AuthRoutes:
    session: AsyncSession = Depends(get_session)
    service: AuthService = Depends(get_auth_service)

    @router.post(
        "/token",
        response_model=TokenResponse,
        status_code=status.HTTP_200_OK,
        summary="Exchange credentials for an access token",
        openapi_extra={"security": []},
    )
    async def issue_token(self, form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
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
        _current_user: User = Depends(bind_current_user),
        users_service: UsersService = Depends(get_users_service),
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
        payload: APIKeyIssueRequest = Depends(_parse_api_key_issue_request),
        _current_user: User = Depends(bind_current_user),
    ) -> APIKeyIssueResponse:
        if payload.principal_type is APIKeyPrincipalType.USER:
            email = payload.email
            if email is None:  # pragma: no cover - validated upstream
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Email required for user API keys",
                )
            result = await self.service.issue_api_key_for_email(
                email=email,
                expires_in_days=payload.expires_in_days,
            )
            user = result.user
            principal_id = result.api_key.user_id or (user.id if user else "")
            principal_label = user.email if user else email
        else:
            service_account_id = payload.service_account_id
            if service_account_id is None:  # pragma: no cover - validated upstream
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Service account ID required",
                )
            result = await self.service.issue_api_key_for_service_account(
                service_account_id=service_account_id,
                expires_in_days=payload.expires_in_days,
            )
            account = result.service_account
            principal_id = result.api_key.service_account_id or (
                account.id if account else service_account_id
            )
            principal_label = account.display_name if account else ""

        return APIKeyIssueResponse(
            api_key=result.raw_key,
            principal_type=result.principal_type,
            principal_id=principal_id,
            principal_label=principal_label,
            expires_at=result.api_key.expires_at,
        )

    @router.get(
        "/api-keys",
        response_model=list[APIKeySummary],
        status_code=status.HTTP_200_OK,
        summary="List issued API keys",
    )
    @access_control(require_admin=True)
    async def list_api_keys(self, _: User = Depends(bind_current_user)) -> list[APIKeySummary]:
        records = await self.service.list_api_keys()
        return [
            APIKeySummary(
                api_key_id=record.id,
                principal_type=(
                    APIKeyPrincipalType.USER
                    if record.user_id
                    else APIKeyPrincipalType.SERVICE_ACCOUNT
                ),
                principal_id=record.user_id or record.service_account_id or "",
                principal_label=(
                    record.user.email
                    if record.user_id and record.user is not None
                    else (
                        record.service_account.display_name
                        if record.service_account
                        else ""
                    )
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
        _: User = Depends(bind_current_user),
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
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing authorization code or state")

        state_cookie = request.cookies.get(SSO_STATE_COOKIE)
        if not state_cookie:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing SSO state cookie")

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
