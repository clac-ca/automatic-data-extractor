"""Routes for user-facing operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ..auth.dependencies import bind_current_user
from ..auth.security import access_control
from .dependencies import get_users_service
from .models import User
from .schemas import UserProfile, UserSummary
from .service import UsersService

router = APIRouter(tags=["users"])

UserDep = Annotated[User, Depends(bind_current_user)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
AdminUsersServiceDep = Annotated[
    UsersService,
    Depends(access_control(require_admin=True, service_dependency=get_users_service)),
]


@router.get(
    "/users/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    response_model_exclude_none=True,
    summary="Return the authenticated user profile",
)
async def read_me(
    _: UserDep,
    service: UsersServiceDep,
) -> UserProfile:
    profile = await service.get_profile()
    return profile


@router.get(
    "/users",
    response_model=list[UserSummary],
    status_code=status.HTTP_200_OK,
    summary="List all users (administrator only)",
)
async def list_users(
    _: UserDep,
    service: AdminUsersServiceDep,
) -> list[UserSummary]:
    users = await service.list_users()
    return users


__all__ = ["router"]
