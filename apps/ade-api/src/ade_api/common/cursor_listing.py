from __future__ import annotations

import base64
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generic, TypeVar
from functools import cmp_to_key
from uuid import UUID

from fastapi import HTTPException, Query, Request, status
from pydantic import Field
from sqlalchemy import and_, false, func, or_, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.operators import desc_op

from ade_api.common.list_filters import FilterItem, FilterJoinOperator, parse_filter_items
from ade_api.common.schema import BaseSchema
from ade_api.common.search import parse_q
from ade_api.common.sorting import parse_sort
from ade_api.common.validators import normalize_utc
from ade_api.settings import COUNT_STATEMENT_TIMEOUT_MS

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_FILTERS = 25
MAX_FILTERS_RAW_LENGTH = 8 * 1024
CURSOR_VERSION = 1

CURSOR_QUERY_KEYS = {
    "limit",
    "cursor",
    "sort",
    "filters",
    "joinOperator",
    "q",
    "includeTotal",
    "includeFacets",
}
STATUS_FILTER_EXAMPLE = '[{"id":"status","operator":"in","value":["processing","failed"]}]'
JOIN_OPERATOR_QUERY = Query(
    FilterJoinOperator.AND,
    alias="joinOperator",
    description="Logical operator to join filters (and/or).",
)


@dataclass(frozen=True)
class CursorQueryParams:
    limit: int
    cursor: str | None
    sort: list[str]
    filters: list[FilterItem]
    join_operator: FilterJoinOperator
    q: str | None
    include_total: bool
    include_facets: bool


class CursorMeta(BaseSchema):
    limit: int
    has_more: bool = Field(alias="hasMore")
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    total_included: bool = Field(alias="totalIncluded")
    total_count: int | None = Field(default=None, alias="totalCount")
    changes_cursor: str | None = Field(default=None, alias="changesCursor")


class CursorPage(BaseSchema, Generic[T]):
    items: Sequence[T]
    meta: CursorMeta
    facets: dict[str, Any] | None = None


@dataclass(frozen=True)
class CursorToken:
    sort: list[str]
    values: list[Any]


@dataclass(frozen=True)
class CursorFieldSpec(Generic[T]):
    key: Callable[[T], Sequence[Any]]
    parse: Callable[[Sequence[Any]], Sequence[Any]]
    directions: Callable[[bool], Sequence[str]]
    arity: int


@dataclass(frozen=True)
class ResolvedCursorField(Generic[T]):
    field_id: str
    order_by: tuple[ColumnElement[Any], ...]
    directions: tuple[str, ...]
    spec: CursorFieldSpec[T]


@dataclass(frozen=True)
class ResolvedCursorSort(Generic[T]):
    tokens: list[str]
    fields: list[ResolvedCursorField[T]]
    order_by: tuple[ColumnElement[Any], ...]


def cursor_query_params(
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Items per page (max {MAX_LIMIT})",
    ),
    cursor: str | None = Query(
        None,
        description="Opaque cursor token for pagination.",
    ),
    sort: str | None = Query(
        None,
        description="JSON array of {id, desc}.",
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
    include_total: bool = Query(
        False,
        alias="includeTotal",
        description="Include totalCount in the response.",
    ),
    include_facets: bool = Query(
        False,
        alias="includeFacets",
        description="Include facet counts in the response.",
    ),
) -> CursorQueryParams:
    sort_tokens = parse_sort(sort)
    filter_items = parse_filter_items(
        filters,
        max_filters=MAX_FILTERS,
        max_raw_length=MAX_FILTERS_RAW_LENGTH,
    )
    q_value = parse_q(q).normalized

    return CursorQueryParams(
        limit=limit,
        cursor=cursor,
        sort=sort_tokens,
        filters=filter_items,
        join_operator=join_operator,
        q=q_value,
        include_total=include_total,
        include_facets=include_facets,
    )


def strict_cursor_query_guard(*, allowed_extra: set[str] | None = None):
    allowed = CURSOR_QUERY_KEYS | (allowed_extra or set())

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


def _is_desc(ordering: ColumnElement[Any]) -> bool:
    return getattr(ordering, "modifier", None) is desc_op


def _normalize_order_by(ordering: ColumnElement[Any] | Sequence[ColumnElement[Any]]) -> tuple[ColumnElement[Any], ...]:
    if isinstance(ordering, (list, tuple)):
        return tuple(ordering)
    return (ordering,)


def resolve_cursor_sort(
    tokens: Iterable[str],
    *,
    allowed: Mapping[str, tuple[ColumnElement[Any], ColumnElement[Any]]],
    cursor_fields: Mapping[str, CursorFieldSpec[T]],
    default: Sequence[str],
    id_field: tuple[ColumnElement[Any], ColumnElement[Any]],
) -> ResolvedCursorSort[T]:
    materialized = list(tokens) or list(default)
    if not materialized:
        raise HTTPException(status_code=422, detail="No sort tokens provided.")

    fields: list[ResolvedCursorField[T]] = []
    order_by: list[ColumnElement[Any]] = []
    tokens_out: list[str] = []
    first_desc: bool | None = None
    names: list[str] = []

    for token in materialized:
        descending = token.startswith("-")
        name = token[1:] if descending else token
        names.append(name)
        spec = cursor_fields.get(name)
        if spec is None:
            allowed_list = ", ".join(sorted(cursor_fields.keys()))
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported sort field '{name}'. Allowed: {allowed_list}",
            )
        columns = allowed.get(name)
        if columns is None:
            allowed_list = ", ".join(sorted(allowed.keys()))
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported sort field '{name}'. Allowed: {allowed_list}",
            )
        chosen = columns[1] if descending else columns[0]
        resolved = _normalize_order_by(chosen)
        directions = tuple("desc" if _is_desc(col) else "asc" for col in resolved)
        if spec.arity != len(resolved):
            raise HTTPException(
                status_code=422,
                detail=f"Cursor field '{name}' must provide {len(resolved)} value(s).",
            )
        fields.append(
            ResolvedCursorField(
                field_id=name,
                order_by=resolved,
                directions=directions,
                spec=spec,
            )
        )
        order_by.extend(resolved)
        tokens_out.append(f"-{name}" if descending else name)
        if first_desc is None:
            first_desc = descending

    if "id" not in names:
        descending = bool(first_desc)
        id_spec = cursor_fields.get("id")
        if id_spec is None:
            raise HTTPException(status_code=422, detail="Cursor sort requires an id field.")
        chosen = id_field[1] if descending else id_field[0]
        resolved = _normalize_order_by(chosen)
        directions = tuple("desc" if _is_desc(col) else "asc" for col in resolved)
        if id_spec.arity != len(resolved):
            raise HTTPException(
                status_code=422,
                detail="Cursor id field must provide a single value.",
            )
        fields.append(
            ResolvedCursorField(
                field_id="id",
                order_by=resolved,
                directions=directions,
                spec=id_spec,
            )
        )
        order_by.extend(resolved)
        tokens_out.append("-id" if descending else "id")

    return ResolvedCursorSort(tokens=tokens_out, fields=fields, order_by=tuple(order_by))


def resolve_cursor_sort_sequence(
    tokens: Iterable[str],
    *,
    cursor_fields: Mapping[str, CursorFieldSpec[T]],
    default: Sequence[str],
) -> ResolvedCursorSort[T]:
    materialized = list(tokens) or list(default)
    if not materialized:
        raise HTTPException(status_code=422, detail="No sort tokens provided.")

    fields: list[ResolvedCursorField[T]] = []
    tokens_out: list[str] = []
    names: list[str] = []
    first_desc: bool | None = None

    for token in materialized:
        descending = token.startswith("-")
        name = token[1:] if descending else token
        names.append(name)
        spec = cursor_fields.get(name)
        if spec is None:
            allowed_list = ", ".join(sorted(cursor_fields.keys()))
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported sort field '{name}'. Allowed: {allowed_list}",
            )
        directions = tuple(spec.directions(descending))
        if len(directions) != spec.arity:
            raise HTTPException(
                status_code=422,
                detail=f"Cursor field '{name}' must provide {spec.arity} direction(s).",
            )
        fields.append(
            ResolvedCursorField(
                field_id=name,
                order_by=(),
                directions=directions,
                spec=spec,
            )
        )
        tokens_out.append(f"-{name}" if descending else name)
        if first_desc is None:
            first_desc = descending

    if "id" not in names:
        descending = bool(first_desc)
        id_spec = cursor_fields.get("id")
        if id_spec is None:
            raise HTTPException(status_code=422, detail="Cursor sort requires an id field.")
        directions = tuple(id_spec.directions(descending))
        fields.append(
            ResolvedCursorField(
                field_id="id",
                order_by=(),
                directions=directions,
                spec=id_spec,
            )
        )
        tokens_out.append("-id" if descending else "id")

    return ResolvedCursorSort(tokens=tokens_out, fields=fields, order_by=tuple())


def encode_cursor(*, sort: Sequence[str], values: Sequence[Any]) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "sort": list(sort),
        "values": [serialize_cursor_value(value) for value in values],
    }
    raw = json.dumps(payload, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")
    return encoded.rstrip("=")


def decode_cursor(token: str) -> CursorToken:
    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=422,
            detail="Invalid cursor token.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid cursor token.")
    if payload.get("v") != CURSOR_VERSION:
        raise HTTPException(status_code=422, detail="Unsupported cursor token.")
    sort = payload.get("sort")
    values = payload.get("values")
    if not isinstance(sort, list) or not isinstance(values, list):
        raise HTTPException(status_code=422, detail="Invalid cursor token.")
    return CursorToken(sort=[str(item) for item in sort], values=values)


def serialize_cursor_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _compare_eq(expr: ColumnElement[Any], value: Any):
    if value is None:
        return expr.is_(None)
    return expr == value


def _compare_after(expr: ColumnElement[Any], value: Any, direction: str):
    if value is None:
        return None
    if direction == "desc":
        return expr < value
    return expr > value


def _unwrap_ordering(expr: ColumnElement[Any]) -> ColumnElement[Any]:
    return getattr(expr, "element", expr)


def _build_cursor_predicate(
    fields: Sequence[ResolvedCursorField[T]],
    values: Sequence[Any],
) -> ColumnElement[Any]:
    keys: list[tuple[ColumnElement[Any], str, Any]] = []
    idx = 0
    for field in fields:
        segment = values[idx : idx + field.spec.arity]
        idx += field.spec.arity
        for expr, direction, value in zip(field.order_by, field.directions, segment):
            keys.append((expr, direction, value))

    if not keys:
        return false()

    conditions = []
    for i, (expr, direction, value) in enumerate(keys):
        eq_conditions = [
            _compare_eq(_unwrap_ordering(eq_expr), eq_value)
            for eq_expr, _, eq_value in keys[:i]
        ]
        comp = _compare_after(_unwrap_ordering(expr), value, direction)
        if comp is None:
            continue
        conditions.append(and_(*eq_conditions, comp))

    if not conditions:
        return false()
    return or_(*conditions)


def _parse_cursor_values(
    token: CursorToken,
    resolved: ResolvedCursorSort[T],
) -> list[Any]:
    if token.sort != resolved.tokens:
        raise HTTPException(
            status_code=422,
            detail="Cursor sort does not match the requested sort.",
        )
    expected = sum(field.spec.arity for field in resolved.fields)
    if len(token.values) != expected:
        raise HTTPException(status_code=422, detail="Cursor values are invalid.")

    parsed: list[Any] = []
    index = 0
    for field in resolved.fields:
        segment = token.values[index : index + field.spec.arity]
        index += field.spec.arity
        parsed_values = list(field.spec.parse(segment))
        if len(parsed_values) != field.spec.arity:
            raise HTTPException(status_code=422, detail="Cursor values are invalid.")
        parsed.extend(parsed_values)
    return parsed


def paginate_query_cursor(
    session: Session,
    stmt: Select,
    *,
    resolved_sort: ResolvedCursorSort[T],
    limit: int,
    cursor: str | None,
    include_total: bool = False,
    changes_cursor: str | None = None,
    row_mapper: Callable[[Mapping[str, Any]], T] | None = None,
) -> CursorPage[T]:
    if (
        include_total
        and COUNT_STATEMENT_TIMEOUT_MS
        and session.bind is not None
        and getattr(session.bind.dialect, "name", None) == "postgresql"
    ):
        session.execute(text(f"SET LOCAL statement_timeout = {int(COUNT_STATEMENT_TIMEOUT_MS)}"))

    count: int | None = None
    if include_total:
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        count = session.execute(count_stmt).scalar_one()

    ordered_stmt = stmt.order_by(*resolved_sort.order_by)

    if cursor:
        token = decode_cursor(cursor)
        values = _parse_cursor_values(token, resolved_sort)
        predicate = _build_cursor_predicate(resolved_sort.fields, values)
        ordered_stmt = ordered_stmt.where(predicate)

    result = session.execute(ordered_stmt.limit(limit + 1))
    if row_mapper is None:
        rows = result.scalars().all()
    else:
        rows = [row_mapper(row) for row in result.mappings().all()]
    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        cursor_values: list[Any] = []
        for field in resolved_sort.fields:
            cursor_values.extend(field.spec.key(last_item))
        next_cursor = encode_cursor(sort=resolved_sort.tokens, values=cursor_values)

    meta = CursorMeta(
        limit=limit,
        has_more=has_more,
        next_cursor=next_cursor,
        total_included=include_total,
        total_count=count if include_total else None,
        changes_cursor=str(changes_cursor) if changes_cursor is not None else None,
    )

    return CursorPage(items=items, meta=meta, facets=None)


def paginate_sequence_cursor(
    items: Sequence[T],
    *,
    resolved_sort: ResolvedCursorSort[T],
    limit: int,
    cursor: str | None,
    include_total: bool = False,
    changes_cursor: str | None = None,
) -> CursorPage[T]:
    total = len(items)
    if not items:
        meta = CursorMeta(
            limit=limit,
            has_more=False,
            next_cursor=None,
            total_included=include_total,
            total_count=total if include_total else None,
            changes_cursor=str(changes_cursor) if changes_cursor is not None else None,
        )
        return CursorPage(items=[], meta=meta, facets=None)

    def sort_key(item: T) -> tuple[Any, ...]:
        values: list[Any] = []
        for field in resolved_sort.fields:
            values.extend(field.spec.key(item))
        return tuple(values)

    directions: list[str] = []
    for field in resolved_sort.fields:
        directions.extend(field.directions)

    def compare(lhs: tuple[Any, ...], rhs: tuple[Any, ...]) -> int:
        for (l_val, r_val, direction) in zip(lhs, rhs, directions):
            if l_val == r_val:
                continue
            if l_val is None and r_val is None:
                continue
            if l_val is None:
                return 1
            if r_val is None:
                return -1
            if direction == "desc":
                return -1 if l_val > r_val else 1
            return -1 if l_val < r_val else 1
        return 0

    ordered = sorted(items, key=cmp_to_key(lambda left, right: compare(sort_key(left), sort_key(right))))
    start_index = 0

    if cursor:
        token = decode_cursor(cursor)
        values = _parse_cursor_values(token, resolved_sort)
        cursor_key = tuple(values)
        for index, item in enumerate(ordered):
            if compare(sort_key(item), cursor_key) == 1:
                start_index = index
                break
        else:
            start_index = len(ordered)

    page_items = ordered[start_index : start_index + limit + 1]
    has_more = len(page_items) > limit
    page_items = page_items[:limit]

    next_cursor = None
    if has_more and page_items:
        cursor_values = list(sort_key(page_items[-1]))
        next_cursor = encode_cursor(sort=resolved_sort.tokens, values=cursor_values)

    meta = CursorMeta(
        limit=limit,
        has_more=has_more,
        next_cursor=next_cursor,
        total_included=include_total,
        total_count=total if include_total else None,
        changes_cursor=str(changes_cursor) if changes_cursor is not None else None,
    )

    return CursorPage(items=page_items, meta=meta, facets=None)


def cursor_field(
    key: Callable[[T], Any],
    parse: Callable[[Any], Any],
) -> CursorFieldSpec[T]:
    return CursorFieldSpec(
        key=lambda item: [key(item)],
        parse=lambda values: [parse(values[0])],
        directions=lambda descending: ["desc" if descending else "asc"],
        arity=1,
    )


def cursor_field_nulls_last(
    key: Callable[[T], Any],
    parse: Callable[[Any], Any],
) -> CursorFieldSpec[T]:
    def _values(item: T) -> list[Any]:
        value = key(item)
        null_rank = 1 if value is None else 0
        return [null_rank, value]

    def _parse(values: Sequence[Any]) -> list[Any]:
        raw = values[1] if len(values) > 1 else None
        return [int(values[0]), parse(raw)]

    return CursorFieldSpec(
        key=_values,
        parse=_parse,
        directions=lambda descending: ["asc", "desc" if descending else "asc"],
        arity=2,
    )


def parse_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid cursor value.") from exc


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return normalize_utc(str(value))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid cursor value.") from exc


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid cursor value.") from exc


def parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0"}:
            return False
    raise HTTPException(status_code=422, detail="Invalid cursor value.")


def parse_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def parse_enum(enum_type: type[Enum]) -> Callable[[Any], Enum | None]:
    def _parse(value: Any) -> Enum | None:
        if value is None:
            return None
        if isinstance(value, enum_type):
            return value
        try:
            return enum_type(str(value))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid cursor value.") from exc

    return _parse


__all__ = [
    "CURSOR_QUERY_KEYS",
    "CursorFieldSpec",
    "CursorMeta",
    "CursorPage",
    "CursorQueryParams",
    "CursorToken",
    "ResolvedCursorField",
    "ResolvedCursorSort",
    "cursor_field",
    "cursor_field_nulls_last",
    "cursor_query_params",
    "decode_cursor",
    "encode_cursor",
    "paginate_query_cursor",
    "paginate_sequence_cursor",
    "parse_bool",
    "parse_datetime",
    "parse_enum",
    "parse_int",
    "parse_str",
    "parse_uuid",
    "resolve_cursor_sort",
    "resolve_cursor_sort_sequence",
    "strict_cursor_query_guard",
]
