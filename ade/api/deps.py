"""Shared FastAPI dependency aliases for ADE API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ade.db.session import get_session
from ade.features.auth.dependencies import get_current_identity, get_current_user
from ade.features.auth.service import AuthenticatedIdentity
from ade.features.users.models import User
from ade.core.pagination import PaginationParams


def get_pagination_params(
    page: Annotated[
        int,
        Query(
            ge=1,
            description="1-based page number.",
            example=1,
        ),
    ] = 1,
    per_page: Annotated[
        int,
        Query(
            ge=1,
            le=200,
            description="Maximum number of items to return per page (1-200).",
            example=50,
        ),
    ] = 50,
    include_total: Annotated[
        bool,
        Query(
            description="Include an exact total count alongside the current page.",
            example=False,
        ),
    ] = False,
) -> PaginationParams:
    """Return validated pagination parameters for list endpoints."""

    return PaginationParams(page=page, per_page=per_page, include_total=include_total)

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CurrentIdentity = Annotated[AuthenticatedIdentity, Depends(get_current_identity)]
CurrentUser = Annotated[User, Depends(get_current_user)]
PaginationParamsDependency = Annotated[
    PaginationParams,
    Depends(get_pagination_params),
]

__all__ = [
    "SessionDependency",
    "CurrentIdentity",
    "CurrentUser",
    "PaginationParamsDependency",
    "get_pagination_params",
]
