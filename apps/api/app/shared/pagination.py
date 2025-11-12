from __future__ import annotations

from collections.abc import Iterable, Sequence
from itertools import islice
from typing import Any, Generic, TypeVar

from apps.api.app.settings import (
    COUNT_STATEMENT_TIMEOUT_MS,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)
from apps.api.app.shared.core.schema import BaseSchema
from pydantic import Field, conint
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

T = TypeVar("T")


class PageParams(BaseSchema):
    """Standard query parameters for paginated list endpoints."""

    page: conint(ge=1) = Field(1, description="1-based page number")
    page_size: conint(ge=1, le=MAX_PAGE_SIZE) = Field(
        DEFAULT_PAGE_SIZE,
        description=f"Items per page (max {MAX_PAGE_SIZE})",
    )
    include_total: bool = Field(
        False, description="Include total item count for the query"
    )


class Page(BaseSchema, Generic[T]):
    """Uniform response envelope for list endpoints."""

    items: Sequence[T]
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
    total: int | None = None


async def paginate_sql(
    session: AsyncSession,
    stmt: Select,
    *,
    page: int,
    page_size: int,
    order_by: Sequence[ColumnElement[Any]],
    include_total: bool = False,
) -> Page[T]:
    """Execute ``stmt`` with limit/offset pagination."""

    offset = (page - 1) * page_size
    ordered_stmt = stmt.order_by(*order_by)

    if include_total:
        if (
            COUNT_STATEMENT_TIMEOUT_MS
            and session.bind is not None
            and getattr(session.bind.dialect, "name", None) == "postgresql"
        ):
            await session.execute(
                text(
                    f"SET LOCAL statement_timeout = {int(COUNT_STATEMENT_TIMEOUT_MS)}"
                )
            )
        count_stmt = select(func.count()).select_from(ordered_stmt.order_by(None).subquery())
        total = (await session.execute(count_stmt)).scalar_one()
        result = await session.execute(
            ordered_stmt.limit(page_size).offset(offset)
        )
        rows = result.scalars().all()
        has_next = (page * page_size) < total
    else:
        result = await session.execute(
            ordered_stmt.limit(page_size + 1).offset(offset)
        )
        rows = result.scalars().all()
        has_next = len(rows) > page_size
        rows = rows[:page_size]
        total = None

    return Page(
        items=rows,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_previous=page > 1,
        total=total,
    )


def paginate_sequence(
    iterable: Iterable[T],
    *,
    page: int,
    page_size: int,
    include_total: bool = False,
) -> Page[T]:
    """Paginate an in-memory sequence using the same envelope."""

    start = (page - 1) * page_size
    if include_total:
        data = list(iterable)
        total = len(data)
        items = data[start : start + page_size]
        has_next = start + page_size < total
        total_value: int | None = total
    else:
        window = list(islice(iterable, start, start + page_size + 1))
        has_next = len(window) > page_size
        items = window[:page_size]
        total_value = None

    return Page(
        items=items,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_previous=page > 1,
        total=total_value,
    )


__all__ = ["Page", "PageParams", "paginate_sequence", "paginate_sql"]
