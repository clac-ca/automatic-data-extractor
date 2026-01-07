from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from fastapi import HTTPException, Query, Request, status
from pydantic import Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from ade_api.common.list_filters import FilterItem, FilterJoinOperator, parse_filter_items
from ade_api.common.schema import BaseSchema
from ade_api.common.search import MAX_QUERY_LENGTH, parse_q
from ade_api.common.sorting import parse_sort
from ade_api.settings import COUNT_STATEMENT_TIMEOUT_MS

T = TypeVar("T")

DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 200
MAX_FILTERS = 25
MAX_FILTERS_RAW_LENGTH = 8 * 1024

LIST_QUERY_KEYS = {"page", "perPage", "sort", "filters", "joinOperator", "q"}
STATUS_FILTER_EXAMPLE = '[{"id":"status","operator":"in","value":["processing","failed"]}]'
JOIN_OPERATOR_QUERY = Query(
    FilterJoinOperator.AND,
    alias="joinOperator",
    description="Logical operator to join filters (and/or).",
)


@dataclass(frozen=True)
class ListQueryParams:
    page: int
    per_page: int
    sort: list[str]
    filters: list[FilterItem]
    join_operator: FilterJoinOperator
    q: str | None


class ListPage(BaseSchema, Generic[T]):
    items: Sequence[T]
    page: int
    per_page: int = Field(alias="perPage")
    page_count: int = Field(alias="pageCount")
    total: int
    changes_cursor: str = Field(alias="changesCursor")


def list_query_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    per_page: int = Query(
        DEFAULT_PER_PAGE,
        ge=1,
        le=MAX_PER_PAGE,
        alias="perPage",
        description=f"Items per page (max {MAX_PER_PAGE})",
    ),
    sort: str | None = Query(
        None,
        description="CSV list of sort keys; prefix '-' for DESC.",
    ),
    filters: str | None = Query(
        None,
        description="URL-encoded JSON array of filter objects.",
        examples={
            "statusIn": {
                "summary": "Status filter",
                "value": STATUS_FILTER_EXAMPLE,
            }
        },
    ),
    join_operator: FilterJoinOperator = JOIN_OPERATOR_QUERY,
    q: str | None = Query(
        None,
        description=(
            "Free-text search string. Tokens are whitespace-separated, matched case-insensitively "
            "as substrings; tokens shorter than 2 characters are ignored."
        ),
        examples={
            "multiToken": {
                "summary": "Search multiple tokens",
                "value": "acme invoice",
            }
        },
    ),
) -> ListQueryParams:
    sort_tokens = parse_sort(sort)
    filter_items = parse_filter_items(
        filters,
        max_filters=MAX_FILTERS,
        max_raw_length=MAX_FILTERS_RAW_LENGTH,
    )
    q_value = parse_q(q).normalized

    return ListQueryParams(
        page=page,
        per_page=per_page,
        sort=sort_tokens,
        filters=filter_items,
        join_operator=join_operator,
        q=q_value,
    )


def strict_list_query_guard(*, allowed_extra: set[str] | None = None):
    allowed = LIST_QUERY_KEYS | (allowed_extra or set())

    def dependency(request: Request) -> None:
        extras = sorted({key for key in request.query_params.keys() if key not in allowed})
        if not extras:
            return
        detail = [
            {
                "type": "extra_forbidden",
                "loc": ["query", key],
                "msg": "Extra inputs are not permitted",
                "input": request.query_params.get(key),
            }
            for key in extras
        ]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)

    return dependency


async def paginate_query(
    session: AsyncSession,
    stmt: Select,
    *,
    page: int,
    per_page: int,
    order_by: Sequence[ColumnElement[Any]],
    changes_cursor: str = "0",
) -> ListPage[T]:
    offset = (page - 1) * per_page
    ordered_stmt = stmt.order_by(*order_by)

    if (
        COUNT_STATEMENT_TIMEOUT_MS
        and session.bind is not None
        and getattr(session.bind.dialect, "name", None) == "postgresql"
    ):
        await session.execute(
            text(f"SET LOCAL statement_timeout = {int(COUNT_STATEMENT_TIMEOUT_MS)}")
        )

    count_stmt = select(func.count()).select_from(ordered_stmt.order_by(None).subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    page_count = math.ceil(total / per_page) if total > 0 else 0

    result = await session.execute(ordered_stmt.limit(per_page).offset(offset))
    rows = result.scalars().all()

    return ListPage[T](
        items=rows,
        page=page,
        per_page=per_page,
        page_count=page_count,
        total=total,
        changes_cursor=str(changes_cursor),
    )


def paginate_sequence(
    items: Sequence[T],
    *,
    page: int,
    per_page: int,
    changes_cursor: str = "0",
) -> ListPage[T]:
    total = len(items)
    page_count = math.ceil(total / per_page) if total > 0 else 0
    offset = (page - 1) * per_page
    page_items = items[offset : offset + per_page]
    return ListPage[T](
        items=page_items,
        page=page,
        per_page=per_page,
        page_count=page_count,
        total=total,
        changes_cursor=str(changes_cursor),
    )


__all__ = [
    "DEFAULT_PER_PAGE",
    "LIST_QUERY_KEYS",
    "ListPage",
    "ListQueryParams",
    "MAX_FILTERS",
    "MAX_FILTERS_RAW_LENGTH",
    "MAX_PER_PAGE",
    "MAX_QUERY_LENGTH",
    "list_query_params",
    "paginate_query",
    "paginate_sequence",
    "strict_list_query_guard",
]
