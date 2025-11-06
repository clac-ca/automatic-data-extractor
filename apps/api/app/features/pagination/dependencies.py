"""Shared pagination dependency providers for features."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from apps.api.app.shared.core.pagination import PaginationParams


def get_pagination_params(
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    per_page: Annotated[int, Query(ge=1, le=200, description="Maximum number of items to return per page (1-200).")]=50,
    include_total: Annotated[bool, Query(description="Include an exact total count alongside the current page.")] = False,
) -> PaginationParams:
    """Return validated pagination parameters for list endpoints."""

    return PaginationParams(page=page, per_page=per_page, include_total=include_total)


__all__ = ["get_pagination_params"]
