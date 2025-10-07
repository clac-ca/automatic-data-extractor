"""Routes for user-facing operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

from ..auth.dependencies import bind_current_user, require_admin_user
from .models import User
from .schemas import UserProfile, UserSummary
from .service import UsersService

router = APIRouter(tags=["users"])


@router.get(
    "/users/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    response_model_exclude_none=True,
    summary="Return the authenticated user profile",
)
async def read_me(
    user: Annotated[User, Depends(bind_current_user)],
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
    _: Annotated[User, Depends(require_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[UserSummary]:
    service = UsersService(session=session)
    users = await service.list_users()
    return users


__all__ = ["router"]
