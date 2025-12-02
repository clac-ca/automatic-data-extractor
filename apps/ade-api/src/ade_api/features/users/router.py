"""Routes for user-facing operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security, status

from ade_api.app.dependencies import get_users_service
from ade_api.common.pagination import PageParams
from ade_api.common.sorting import make_sort_dependency
from ade_api.common.types import OrderBy
from ade_api.core.http import require_authenticated, require_global
from ade_api.core.models import User

from .filters import UserFilters
from .schemas import UserPage
from .service import UsersService
from .sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(tags=["users"], dependencies=[Security(require_authenticated)])


get_sort_order = make_sort_dependency(
    allowed=SORT_FIELDS,
    default=DEFAULT_SORT,
    id_field=ID_FIELD,
)


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


__all__ = ["router"]
