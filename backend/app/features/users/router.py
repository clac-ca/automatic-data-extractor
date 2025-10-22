"""Routes for user-facing operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security, status

from backend.app.features.auth.dependencies import require_authenticated
from backend.app.features.roles.dependencies import require_global

from .dependencies import get_users_service
from .models import User
from .schemas import UserProfile, UserSummary
from .service import UsersService

router = APIRouter(tags=["users"], dependencies=[Security(require_authenticated)])


@router.get(
    "/users/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    response_model_exclude_none=True,
    summary="Return the authenticated user profile",
)
async def read_me(
    user: Annotated[User, Security(require_authenticated)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserProfile:
    profile = await service.get_profile(user=user)
    return profile


@router.get(
    "/users",
    response_model=list[UserSummary],
    status_code=status.HTTP_200_OK,
    summary="List all users (administrator only)",
)
async def list_users(
    _: Annotated[User, Security(require_global("Users.Read.All"))],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> list[UserSummary]:
    users = await service.list_users()
    return users


__all__ = ["router"]
