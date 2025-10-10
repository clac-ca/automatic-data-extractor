"""Routes for user-facing operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from ade.api.security import require_authenticated, require_global
from ade.db.session import get_session

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
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserProfile:
    service = UsersService(session=session)
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
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[UserSummary]:
    service = UsersService(session=session)
    users = await service.list_users()
    return users


__all__ = ["router"]
