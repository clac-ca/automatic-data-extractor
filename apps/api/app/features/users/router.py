"""Routes for user-facing operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security, status

from apps.api.app.shared.dependency import (
    get_users_service,
    require_authenticated,
    require_global,
)
from apps.api.app.shared.pagination import PageParams
from apps.api.app.shared.sorting import make_sort_dependency
from apps.api.app.shared.types import OrderBy

from .filters import UserFilters
from .models import User
from .schemas import UserPage, UserProfile
from .service import UsersService
from .sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(tags=["users"], dependencies=[Security(require_authenticated)])


get_sort_order = make_sort_dependency(
    allowed=SORT_FIELDS,
    default=DEFAULT_SORT,
    id_field=ID_FIELD,
)


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
    response_model=UserPage,
    status_code=status.HTTP_200_OK,
    summary="List all users (administrator only)",
    response_model_exclude_none=True,
)
async def list_users(
    _: Annotated[User, Security(require_global("Users.Read.All"))],
    page: Annotated[PageParams, Depends()],
    filters: Annotated[UserFilters, Depends()],
    order_by: Annotated[OrderBy, Depends(get_sort_order)],
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserPage:
    return await service.list_users(
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
        order_by=order_by,
        filters=filters,
    )


__all__ = ["router"]
