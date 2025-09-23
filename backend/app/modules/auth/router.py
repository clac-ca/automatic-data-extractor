"""Routes for authentication flows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..users.dependencies import get_users_service
from ..users.models import User
from ..users.schemas import UserProfile
from ..users.service import UsersService
from .dependencies import bind_current_user, get_auth_service
from .schemas import TokenResponse
from .service import AuthService


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
        current_user: User = Depends(bind_current_user),
        users_service: UsersService = Depends(get_users_service),
    ) -> UserProfile:
        """Return profile information for the active user."""

        profile = await users_service.get_profile()
        return profile


__all__ = ["router"]
