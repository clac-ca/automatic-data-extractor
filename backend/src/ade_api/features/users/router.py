"""Routes for user-facing operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Security, status

from ade_api.api.deps import get_users_service, get_users_service_read
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort,
    strict_cursor_query_guard,
)
from ade_api.core.http import require_authenticated, require_csrf, require_global
from ade_db.models import User

from .schemas import UserOut, UserPage, UserUpdate
from .service import UsersService
from .sorting import CURSOR_FIELDS, DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(tags=["users"], dependencies=[Security(require_authenticated)])


USER_UPDATE_BODY = Body(
    ...,
    description="Fields to update on the user record.",
)
USER_ID_PARAM = Annotated[
    UUID,
    Path(
        description="User identifier.",
        alias="userId",
    ),
]


@router.get(
    "/users",
    response_model=UserPage,
    status_code=status.HTTP_200_OK,
    summary="List all users (administrator only)",
    response_model_exclude_none=True,
)
def list_users(
    _: Annotated[User, Security(require_global("users.read_all"))],
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
    service: Annotated[UsersService, Depends(get_users_service_read)],
) -> UserPage:
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    return service.list_users(
        limit=list_query.limit,
        cursor=list_query.cursor,
        resolved_sort=resolved_sort,
        include_total=list_query.include_total,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
    )


@router.get(
    "/users/{userId}",
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
def get_user(
    _: Annotated[User, Security(require_global("users.read_all"))],
    user_id: USER_ID_PARAM,
    service: Annotated[UsersService, Depends(get_users_service_read)],
) -> UserOut:
    return service.get_user(user_id=user_id)


@router.patch(
    "/users/{userId}",
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
def update_user(
    actor: Annotated[User, Security(require_global("users.manage_all"))],
    user_id: USER_ID_PARAM,
    service: Annotated[UsersService, Depends(get_users_service)],
    payload: UserUpdate = USER_UPDATE_BODY,
) -> UserOut:
    return service.update_user(user_id=user_id, payload=payload, actor=actor)


@router.post(
    "/users/{userId}/deactivate",
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
def deactivate_user(
    actor: Annotated[User, Security(require_global("users.manage_all"))],
    user_id: USER_ID_PARAM,
    service: Annotated[UsersService, Depends(get_users_service)],
) -> UserOut:
    return service.deactivate_user(user_id=user_id, actor=actor)


__all__ = ["router"]
