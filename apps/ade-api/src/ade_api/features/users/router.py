"""Routes for user-facing operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Security, status

from ade_api.api.deps import get_users_service
from ade_api.common.pagination import PageParams
from ade_api.common.sorting import make_sort_dependency
from ade_api.common.types import OrderBy
from ade_api.core.http import require_authenticated, require_csrf, require_global
from ade_api.models import User

from .filters import UserFilters
from .schemas import UserOut, UserPage, UserUpdate
from .service import UsersService
from .sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(tags=["users"], dependencies=[Security(require_authenticated)])


get_sort_order = make_sort_dependency(
    allowed=SORT_FIELDS,
    default=DEFAULT_SORT,
    id_field=ID_FIELD,
)

USER_UPDATE_BODY = Body(
    ...,
    description="Fields to update on the user record.",
)
USER_ID_PARAM = Annotated[
    UUID,
    Path(
        description="User identifier.",
    ),
]


@router.get(
    "/users",
    response_model=UserPage,
    status_code=status.HTTP_200_OK,
    summary="List all users (administrator only)",
    response_model_exclude_none=True,
)
async def list_users(
    _: Annotated[User, Security(require_global("users.read_all"))],
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


@router.get(
    "/users/{user_id}",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a user (administrator only)",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to read users.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Global users.read_all permission required.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found.",
        },
    },
)
async def get_user(
    _: Annotated[User, Security(require_global("users.read_all"))],
    user_id: USER_ID_PARAM,
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserOut:
    return await service.get_user(user_id=user_id)


@router.patch(
    "/users/{user_id}",
    dependencies=[Security(require_csrf)],
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Update a user (administrator only)",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update users.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Global users.manage_all permission required.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "No valid fields were provided for update.",
        },
    },
)
async def update_user(
    actor: Annotated[User, Security(require_global("users.manage_all"))],
    user_id: USER_ID_PARAM,
    service: Annotated[UsersService, Depends(get_users_service)],
    payload: UserUpdate = USER_UPDATE_BODY,
) -> UserOut:
    return await service.update_user(user_id=user_id, payload=payload, actor=actor)


@router.post(
    "/users/{user_id}/deactivate",
    dependencies=[Security(require_csrf)],
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Deactivate a user and revoke their API keys (administrator only)",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to deactivate users.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Global users.manage_all permission required.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found.",
        },
    },
)
async def deactivate_user(
    actor: Annotated[User, Security(require_global("users.manage_all"))],
    user_id: USER_ID_PARAM,
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserOut:
    return await service.deactivate_user(user_id=user_id, actor=actor)


__all__ = ["router"]
