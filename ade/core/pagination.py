"""Shared pagination helpers for SQLAlchemy queries."""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ClauseElement

from .schema import BaseSchema


class PaginationParams(BaseSchema):
    """Validated pagination parameters."""

    page: int = Field(default=1, ge=1, description="1-based page number.")
    per_page: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Number of items per page (capped at 200).",
    )
    include_total: bool = Field(
        default=False,
        description="Whether to include a total count alongside the page results.",
    )

    @property
    def offset(self) -> int:
        """Return the SQL offset for this page."""

        return (self.page - 1) * self.per_page

    @property
    def window(self) -> int:
        """Return the number of rows to fetch including the lookahead sentinel."""

        return self.per_page + 1


class PaginationEnvelope(BaseSchema):
    """Standardised response envelope for paginated endpoints."""

    items: list[Any] = Field(default_factory=list)
    page: int = Field(ge=1, description="1-based page number.")
    per_page: int = Field(
        ge=1,
        le=200,
        description="Number of items per page returned in this response.",
    )
    has_next: bool = Field(description="Whether another page exists after this one.")
    total: int | None = Field(
        default=None,
        ge=0,
        description="Total number of matching records when requested.",
    )


async def paginate(
    session: AsyncSession,
    query: Select[Any],
    *,
    page: int,
    per_page: int,
    order_by: Sequence[ClauseElement[Any]],
    include_total: bool = False,
) -> dict[str, Any]:
    """Execute ``query`` with limit/offset pagination and return a serialisable envelope."""

    if page < 1:
        raise ValueError("page must be greater than or equal to 1")
    if per_page < 1:
        raise ValueError("per_page must be greater than or equal to 1")

    lookahead = per_page + 1
    offset = (page - 1) * per_page

    ordered = query.order_by(*order_by)
    statement = ordered.offset(offset).limit(lookahead)
    result = await session.execute(statement)
    rows = result.scalars().all()

    has_next = len(rows) > per_page
    if has_next:
        rows = rows[:-1]

    payload: dict[str, Any] = {
        "items": rows,
        "page": page,
        "per_page": per_page,
        "has_next": has_next,
    }

    if include_total:
        count_query = select(func.count()).select_from(ordered.order_by(None).subquery())
        total_result = await session.execute(count_query)
        payload["total"] = int(total_result.scalar_one())

    return payload


__all__ = [
    "PaginationEnvelope",
    "PaginationParams",
    "paginate",
]
