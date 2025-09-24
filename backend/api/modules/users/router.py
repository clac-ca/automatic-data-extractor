"""Routes for user-facing operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ..auth.dependencies import bind_current_user
from ..auth.security import access_control
from .dependencies import get_users_service
from .models import User
from .schemas import UserProfile, UserSummary
from .service import UsersService

router = APIRouter(tags=["users"])


@cbv(router)
class UsersRoutes:
    current_user: User = Depends(bind_current_user)
    session: AsyncSession = Depends(get_session)
    service: UsersService = Depends(get_users_service)

    @router.get(
        "/users/me",
        response_model=UserProfile,
        status_code=status.HTTP_200_OK,
        response_model_exclude_none=True,
        summary="Return the authenticated user profile",
    )
    async def read_me(self) -> UserProfile:
        profile = await self.service.get_profile()
        return profile

    @router.get(
        "/users",
        response_model=list[UserSummary],
        status_code=status.HTTP_200_OK,
        summary="List all users (administrator only)",
    )
    @access_control(require_admin=True)
    async def list_users(self) -> list[UserSummary]:
        users = await self.service.list_users()
        return users


__all__ = ["router"]
