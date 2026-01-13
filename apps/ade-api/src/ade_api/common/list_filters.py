from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement

from ade_api.common.validators import normalize_utc


class FilterOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "notIn"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    ILIKE = "iLike"
    NOT_ILIKE = "notILike"
    IS_EMPTY = "isEmpty"
    IS_NOT_EMPTY = "isNotEmpty"
    BETWEEN = "between"


class FilterJoinOperator(str, Enum):
    AND = "and"
    OR = "or"


class FilterItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    operator: FilterOperator
    value: Any | None = None


class FilterValueType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    UUID = "uuid"
    DATETIME = "datetime"
    ENUM = "enum"


OPERATOR_ALIASES: dict[str, FilterOperator] = {
    "inArray": FilterOperator.IN,
    "notInArray": FilterOperator.NOT_IN,
    "isBetween": FilterOperator.BETWEEN,
    "isRelativeToToday": FilterOperator.BETWEEN,
}

RELATIVE_RANGE_PATTERN = re.compile(r"^(past|last|next)_(\d+)_days$")


@dataclass(frozen=True)
class FilterField:
    id: str
    column: ColumnElement[Any]
    operators: set[FilterOperator]
    value_type: FilterValueType
    enum_type: type[Enum] | None = None


@dataclass(frozen=True)
class ParsedFilter:
    field: FilterField
    operator: FilterOperator
    value: Any | None


class FilterRegistry:
    def __init__(self, fields: Iterable[FilterField]) -> None:
        self._fields = {field.id: field for field in fields}

    def get(self, key: str) -> FilterField | None:
        return self._fields.get(key)

    def keys(self) -> Sequence[str]:
        return tuple(self._fields.keys())


def _epoch_to_datetime(value: float) -> datetime:
    seconds = value / 1000 if abs(value) > 100_000_000_000 else value
    return datetime.fromtimestamp(seconds, tz=UTC)


def _parse_epoch(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _start_of_day(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(value: datetime) -> datetime:
    return value.replace(hour=23, minute=59, second=59, microsecond=999999)


def _start_of_week(value: datetime) -> datetime:
    return _start_of_day(value - timedelta(days=value.weekday()))


def _end_of_week(value: datetime) -> datetime:
    return _end_of_day(_start_of_week(value) + timedelta(days=6))


def _start_of_month(value: datetime) -> datetime:
    return _start_of_day(value.replace(day=1))


def _end_of_month(value: datetime) -> datetime:
    if value.month == 12:
        next_month = value.replace(year=value.year + 1, month=1, day=1)
    else:
        next_month = value.replace(month=value.month + 1, day=1)
    return _end_of_day(next_month - timedelta(days=1))


def _start_of_year(value: datetime) -> datetime:
    return _start_of_day(value.replace(month=1, day=1))


def _end_of_year(value: datetime) -> datetime:
    next_year = value.replace(year=value.year + 1, month=1, day=1)
    return _end_of_day(next_year - timedelta(days=1))


def _resolve_relative_date_range(value: Any) -> list[datetime] | None:
    if value is None:
        return None

    if isinstance(value, list):
        if len(value) != 2 or any(entry in {None, ""} for entry in value):
            return None
        return value

    now = datetime.now(tz=UTC)

    if isinstance(value, (int, float)):
        timestamp = _epoch_to_datetime(float(value))
        return [_start_of_day(timestamp), _end_of_day(timestamp)]

    if isinstance(value, str):
        token = value.strip().lower()
        if not token:
            return None

        if token == "today":
            return [_start_of_day(now), _end_of_day(now)]
        if token == "yesterday":
            yesterday = now - timedelta(days=1)
            return [_start_of_day(yesterday), _end_of_day(yesterday)]
        if token == "tomorrow":
            tomorrow = now + timedelta(days=1)
            return [_start_of_day(tomorrow), _end_of_day(tomorrow)]
        if token == "this_week":
            return [_start_of_week(now), _end_of_week(now)]
        if token == "last_week":
            last_week = now - timedelta(days=7)
            return [_start_of_week(last_week), _end_of_week(last_week)]
        if token == "this_month":
            return [_start_of_month(now), _end_of_month(now)]
        if token == "last_month":
            last_month = (now.replace(day=1) - timedelta(days=1))
            return [_start_of_month(last_month), _end_of_month(last_month)]
        if token == "this_year":
            return [_start_of_year(now), _end_of_year(now)]
        if token == "last_year":
            last_year = now.replace(year=now.year - 1)
            return [_start_of_year(last_year), _end_of_year(last_year)]

        match = RELATIVE_RANGE_PATTERN.match(token)
        if match:
            direction, count_raw = match.groups()
            try:
                count = int(count_raw)
            except ValueError:
                return None
            if count <= 0:
                return None
            if direction in {"past", "last"}:
                start = _start_of_day(now - timedelta(days=count - 1))
                end = _end_of_day(now)
            else:
                start = _start_of_day(now)
                end = _end_of_day(now + timedelta(days=count - 1))
            return [start, end]

        epoch_value = _parse_epoch(token)
        if epoch_value is not None:
            timestamp = _epoch_to_datetime(epoch_value)
            return [_start_of_day(timestamp), _end_of_day(timestamp)]

        try:
            timestamp = normalize_utc(token)
        except ValueError:
            return None
        return [_start_of_day(timestamp), _end_of_day(timestamp)]

    return None


def _clean_filter_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        cleaned: list[Any] = []
        for entry in value:
            if isinstance(entry, str):
                trimmed = entry.strip()
                if not trimmed:
                    continue
                cleaned.append(trimmed)
            else:
                cleaned.append(entry)
        return cleaned

    return value


def _should_skip_filter(operator: str, value: Any) -> bool:
    if operator in {FilterOperator.IS_EMPTY.value, FilterOperator.IS_NOT_EMPTY.value}:
        return False
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, list):
        return len(value) == 0
    return False


def _normalize_filter_raw(raw: dict[str, Any]) -> dict[str, Any] | None:
    raw_operator = raw.get("operator")
    if not isinstance(raw_operator, str):
        return raw

    normalized_operator = OPERATOR_ALIASES.get(raw_operator, raw_operator)
    if isinstance(normalized_operator, FilterOperator):
        normalized_operator_value = normalized_operator.value
    else:
        normalized_operator_value = normalized_operator
    raw_value = _clean_filter_value(raw.get("value"))

    if raw_operator == "isRelativeToToday":
        relative_range = _resolve_relative_date_range(raw_value)
        if relative_range is None:
            return None
        raw_value = relative_range

    if normalized_operator_value in {FilterOperator.IS_EMPTY.value, FilterOperator.IS_NOT_EMPTY.value}:
        raw_value = None

    if normalized_operator_value == FilterOperator.BETWEEN.value:
        if (
            not isinstance(raw_value, list)
            or len(raw_value) != 2
            or any(entry is None or (isinstance(entry, str) and not entry) for entry in raw_value)
        ):
            return None

    if normalized_operator_value in {FilterOperator.IN.value, FilterOperator.NOT_IN.value}:
        if not isinstance(raw_value, list) or len(raw_value) == 0:
            return None

    if _should_skip_filter(normalized_operator_value, raw_value):
        return None

    return {**raw, "operator": normalized_operator_value, "value": raw_value}


def parse_filter_items(
    raw_filters: str | None,
    *,
    max_filters: int,
    max_raw_length: int,
) -> list[FilterItem]:
    if raw_filters is None:
        return []
    candidate = raw_filters.strip()
    if not candidate:
        return []
    if len(candidate) > max_raw_length:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"filters exceeds {max_raw_length} characters",
        )
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="filters must be valid JSON",
        ) from exc
    if not isinstance(decoded, list):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="filters must be a JSON array",
        )
    if len(decoded) > max_filters:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Too many filters (max {max_filters}).",
        )

    items: list[FilterItem] = []
    for index, raw in enumerate(decoded):
        if not isinstance(raw, dict):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Filter #{index + 1} must be an object",
            )
        normalized = _normalize_filter_raw(raw)
        if normalized is None:
            continue
        try:
            item = FilterItem.model_validate(normalized)
        except ValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(),
            ) from exc
        _validate_filter_value_shape(item)
        items.append(item)
    return items


def prepare_filters(
    items: Iterable[FilterItem],
    registry: FilterRegistry,
) -> list[ParsedFilter]:
    parsed: list[ParsedFilter] = []
    for item in items:
        field = registry.get(item.id)
        if field is None:
            allowed = ", ".join(sorted(registry.keys()))
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported filter id '{item.id}'. Allowed: {allowed}",
            )
        if item.operator not in field.operators:
            allowed_ops = ", ".join(sorted(op.value for op in field.operators))
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Unsupported operator '{item.operator.value}' for '{item.id}'. "
                    f"Allowed: {allowed_ops}"
                ),
            )
        value = _coerce_value(item.value, field, item.operator)
        parsed.append(ParsedFilter(field=field, operator=item.operator, value=value))
    return parsed


def build_predicate(parsed: ParsedFilter) -> ColumnElement[Any]:
    column = parsed.field.column
    operator = parsed.operator
    value = parsed.value

    if operator == FilterOperator.EQ:
        return column.is_(None) if value is None else column == value
    if operator == FilterOperator.NE:
        return column.is_not(None) if value is None else column != value
    if operator == FilterOperator.IN:
        return column.in_(value)
    if operator == FilterOperator.NOT_IN:
        return ~column.in_(value)
    if operator == FilterOperator.LT:
        return column < value
    if operator == FilterOperator.LTE:
        return column <= value
    if operator == FilterOperator.GT:
        return column > value
    if operator == FilterOperator.GTE:
        return column >= value
    if operator == FilterOperator.ILIKE:
        return column.ilike(_like_pattern(value))
    if operator == FilterOperator.NOT_ILIKE:
        return ~column.ilike(_like_pattern(value))
    if operator == FilterOperator.IS_EMPTY:
        return column.is_(None)
    if operator == FilterOperator.IS_NOT_EMPTY:
        return column.is_not(None)
    if operator == FilterOperator.BETWEEN:
        return column.between(value[0], value[1])

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unsupported operator '{operator.value}'.",
    )


def combine_predicates(
    predicates: Sequence[ColumnElement[Any]],
    join_operator: FilterJoinOperator,
) -> ColumnElement[Any] | None:
    if not predicates:
        return None
    if join_operator == FilterJoinOperator.OR:
        return or_(*predicates)
    return and_(*predicates)


def _validate_filter_value_shape(item: FilterItem) -> None:
    operator = item.operator
    value = item.value

    if operator in {
        FilterOperator.EQ,
        FilterOperator.NE,
        FilterOperator.LT,
        FilterOperator.LTE,
        FilterOperator.GT,
        FilterOperator.GTE,
        FilterOperator.ILIKE,
        FilterOperator.NOT_ILIKE,
    }:
        if isinstance(value, list):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Filter '{item.id}' with operator '{operator.value}' "
                    "expects a scalar value"
                ),
            )
        if value is None and operator not in {FilterOperator.EQ, FilterOperator.NE}:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Filter '{item.id}' with operator '{operator.value}' "
                    "requires a non-null value"
                ),
            )
        return

    if operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
        if not isinstance(value, list) or not value:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Filter '{item.id}' with operator '{operator.value}' "
                    "expects a non-empty array value"
                ),
            )
        return

    if operator == FilterOperator.BETWEEN:
        if not isinstance(value, list) or len(value) != 2:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Filter '{item.id}' with operator '{operator.value}' "
                    "expects a 2-element array value"
                ),
            )
        if any(entry is None for entry in value):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Filter '{item.id}' with operator '{operator.value}' "
                    "requires two non-null values"
                ),
            )
        return

    if operator in {FilterOperator.IS_EMPTY, FilterOperator.IS_NOT_EMPTY}:
        if value is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Filter '{item.id}' with operator '{operator.value}' "
                    "does not accept a value"
                ),
            )


def _coerce_value(
    value: Any | None,
    field: FilterField,
    operator: FilterOperator,
) -> Any | None:
    if operator in {FilterOperator.IS_EMPTY, FilterOperator.IS_NOT_EMPTY}:
        return None
    if operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
        return [_coerce_scalar(item, field) for item in value or []]
    if operator == FilterOperator.BETWEEN:
        return [_coerce_scalar(item, field) for item in value or []]
    return _coerce_scalar(value, field)


def _coerce_scalar(value: Any | None, field: FilterField) -> Any | None:
    if value is None:
        return None

    value_type = field.value_type

    if value_type == FilterValueType.STRING:
        if isinstance(value, str):
            return value
        return str(value)

    if value_type == FilterValueType.INT:
        if isinstance(value, bool):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Filter '{field.id}' expects an integer value",
            )
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Filter '{field.id}' expects an integer value",
                ) from exc

    if value_type == FilterValueType.FLOAT:
        if isinstance(value, bool):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Filter '{field.id}' expects a number value",
            )
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Filter '{field.id}' expects a number value",
                ) from exc

    if value_type == FilterValueType.BOOL:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Filter '{field.id}' expects a boolean value",
        )

    if value_type == FilterValueType.UUID:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Filter '{field.id}' expects a UUID value",
                ) from exc
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Filter '{field.id}' expects a UUID value",
        )

    if value_type == FilterValueType.DATETIME:
        if isinstance(value, datetime):
            return normalize_utc(value)
        if isinstance(value, (int, float)):
            return _epoch_to_datetime(float(value))
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                epoch_value = _parse_epoch(trimmed)
                if epoch_value is not None:
                    return _epoch_to_datetime(epoch_value)
            try:
                return normalize_utc(value)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Filter '{field.id}' expects an ISO datetime or epoch value",
                ) from exc
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Filter '{field.id}' expects an ISO datetime or epoch value",
        )

    if value_type == FilterValueType.ENUM:
        enum_type = field.enum_type
        if enum_type is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Filter '{field.id}' expects a supported enum value",
            )
        if isinstance(value, enum_type):
            return value
        if isinstance(value, str):
            try:
                return enum_type(value)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Filter '{field.id}' expects a supported enum value",
                ) from exc
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Filter '{field.id}' expects a supported enum value",
        )

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unsupported filter type for '{field.id}'",
    )


def _like_pattern(value: Any) -> str:
    if not isinstance(value, str):
        return "%"
    return value if "%" in value else f"%{value}%"


__all__ = [
    "FilterField",
    "FilterItem",
    "FilterJoinOperator",
    "FilterOperator",
    "FilterRegistry",
    "FilterValueType",
    "ParsedFilter",
    "build_predicate",
    "combine_predicates",
    "parse_filter_items",
    "prepare_filters",
]
