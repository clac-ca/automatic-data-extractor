from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Never
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import and_, or_
from sqlalchemy.orm.attributes import QueryableAttribute
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
    column: ColumnElement[Any] | QueryableAttribute[Any]
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


def _resolve_relative_date_range(value: Any) -> list[Any] | None:
    if value is None:
        return None

    if isinstance(value, list):
        return _resolve_relative_date_list(value)

    now = datetime.now(tz=UTC)

    if isinstance(value, (int, float)):
        timestamp = _epoch_to_datetime(float(value))
        return [_start_of_day(timestamp), _end_of_day(timestamp)]

    if isinstance(value, str):
        token = value.strip().lower()
        if not token:
            return None

        named_range = _resolve_named_relative_range(token, now)
        if named_range is not None:
            return named_range

        dynamic_range = _resolve_relative_range_token(token, now)
        if dynamic_range is not None:
            return dynamic_range

        epoch_value = _parse_epoch(token)
        if epoch_value is not None:
            timestamp = _epoch_to_datetime(epoch_value)
            return [_start_of_day(timestamp), _end_of_day(timestamp)]

        try:
            normalized = normalize_utc(token)
        except ValueError:
            return None
        if normalized is None:
            return None
        return [_start_of_day(normalized), _end_of_day(normalized)]

    return None


def _resolve_relative_date_list(value: list[Any]) -> list[Any] | None:
    if len(value) != 2:
        return None

    start, end = value
    if start is None or end is None:
        return None
    if isinstance(start, str) and not start.strip():
        return None
    if isinstance(end, str) and not end.strip():
        return None
    return [start, end]


def _resolve_named_relative_range(token: str, now: datetime) -> list[datetime] | None:
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
        last_month = now.replace(day=1) - timedelta(days=1)
        return [_start_of_month(last_month), _end_of_month(last_month)]
    if token == "this_year":
        return [_start_of_year(now), _end_of_year(now)]
    if token == "last_year":
        last_year = now.replace(year=now.year - 1)
        return [_start_of_year(last_year), _end_of_year(last_year)]
    return None


def _resolve_relative_range_token(token: str, now: datetime) -> list[datetime] | None:
    match = RELATIVE_RANGE_PATTERN.match(token)
    if not match:
        return None

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

    if normalized_operator_value in {
        FilterOperator.IS_EMPTY.value,
        FilterOperator.IS_NOT_EMPTY.value,
    }:
        raw_value = None

    if _should_skip_filter(normalized_operator_value, raw_value):
        return None

    return {**raw, "operator": normalized_operator_value, "value": raw_value}


def parse_filter_items(
    raw_filters: str | None,
    *,
    max_filters: int,
    max_raw_length: int,
) -> list[FilterItem]:
    decoded = _parse_raw_filters(raw_filters, max_raw_length=max_raw_length)
    if not decoded:
        return []

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


def _parse_raw_filters(
    raw_filters: str | None,
    *,
    max_raw_length: int,
) -> list[Any]:
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

    return decoded


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
    if operator == FilterOperator.BETWEEN:
        if not isinstance(value, list) or len(value) != 2:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Filter '{parsed.field.id}' expects a 2-element array value",
            )
        return column.between(value[0], value[1])

    builder = _PREDICATE_BUILDERS.get(operator)
    if builder is not None:
        return builder(column, value)

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unsupported operator '{operator.value}'.",
    )


_PredicateBuilder = Callable[
    [ColumnElement[Any] | QueryableAttribute[Any], Any],
    ColumnElement[Any],
]
_PREDICATE_BUILDERS: dict[FilterOperator, _PredicateBuilder] = {
    FilterOperator.IN: lambda column, value: column.in_(value),
    FilterOperator.NOT_IN: lambda column, value: ~column.in_(value),
    FilterOperator.LT: lambda column, value: column < value,
    FilterOperator.LTE: lambda column, value: column <= value,
    FilterOperator.GT: lambda column, value: column > value,
    FilterOperator.GTE: lambda column, value: column >= value,
    FilterOperator.ILIKE: lambda column, value: column.ilike(_like_pattern(value)),
    FilterOperator.NOT_ILIKE: lambda column, value: ~column.ilike(_like_pattern(value)),
    FilterOperator.IS_EMPTY: lambda column, _value: column.is_(None),
    FilterOperator.IS_NOT_EMPTY: lambda column, _value: column.is_not(None),
}


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

    if operator in _SCALAR_OPERATORS:
        _validate_scalar_value(item.id, operator, value)
        return

    if operator in _LIST_OPERATORS:
        _validate_list_value(item.id, operator, value)
        return

    if operator == FilterOperator.BETWEEN:
        _validate_between_value(item.id, operator, value)
        return

    if operator in _VALUELESS_OPERATORS:
        _validate_valueless_operator(item.id, operator, value)
        return


_SCALAR_OPERATORS = {
    FilterOperator.EQ,
    FilterOperator.NE,
    FilterOperator.LT,
    FilterOperator.LTE,
    FilterOperator.GT,
    FilterOperator.GTE,
    FilterOperator.ILIKE,
    FilterOperator.NOT_ILIKE,
}
_NULLABLE_SCALAR_OPERATORS = {FilterOperator.EQ, FilterOperator.NE}
_LIST_OPERATORS = {FilterOperator.IN, FilterOperator.NOT_IN}
_VALUELESS_OPERATORS = {FilterOperator.IS_EMPTY, FilterOperator.IS_NOT_EMPTY}


def _validate_scalar_value(
    field_id: str,
    operator: FilterOperator,
    value: Any,
) -> None:
    if isinstance(value, list):
        _raise_filter_shape_error(field_id, operator, "expects a scalar value")
    if value is None and operator not in _NULLABLE_SCALAR_OPERATORS:
        _raise_filter_shape_error(field_id, operator, "requires a non-null value")


def _validate_list_value(
    field_id: str,
    operator: FilterOperator,
    value: Any,
) -> None:
    if not isinstance(value, list) or not value:
        _raise_filter_shape_error(field_id, operator, "expects a non-empty array value")


def _validate_between_value(
    field_id: str,
    operator: FilterOperator,
    value: Any,
) -> None:
    if not isinstance(value, list) or len(value) != 2:
        _raise_filter_shape_error(field_id, operator, "expects a 2-element array value")
    if any(entry is None for entry in value):
        _raise_filter_shape_error(field_id, operator, "requires two non-null values")


def _validate_valueless_operator(
    field_id: str,
    operator: FilterOperator,
    value: Any,
) -> None:
    if value is not None:
        _raise_filter_shape_error(field_id, operator, "does not accept a value")


def _raise_filter_shape_error(
    field_id: str,
    operator: FilterOperator,
    message: str,
) -> Never:
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Filter '{field_id}' with operator '{operator.value}' {message}",
    )


def _coerce_value(
    value: Any | None,
    field: FilterField,
    operator: FilterOperator,
) -> Any | None:
    if operator in _VALUELESS_OPERATORS:
        return None
    if operator in _LIST_OPERATORS:
        return [_coerce_scalar(item, field) for item in value or []]
    if operator == FilterOperator.BETWEEN:
        return [_coerce_scalar(item, field) for item in value or []]
    return _coerce_scalar(value, field)


def _coerce_scalar(value: Any | None, field: FilterField) -> Any | None:
    if value is None:
        return None

    value_type = field.value_type

    if value_type == FilterValueType.STRING:
        return value if isinstance(value, str) else str(value)
    if value_type == FilterValueType.INT:
        return _coerce_int(value, field.id)
    if value_type == FilterValueType.FLOAT:
        return _coerce_float(value, field.id)
    if value_type == FilterValueType.BOOL:
        return _coerce_bool(value, field.id)
    if value_type == FilterValueType.UUID:
        return _coerce_uuid(value, field.id)
    if value_type == FilterValueType.DATETIME:
        return _coerce_datetime(value, field.id)
    if value_type == FilterValueType.ENUM:
        return _coerce_enum(value, field)

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unsupported filter type for '{field.id}'",
    )


def _coerce_int(value: Any, field_id: str) -> int:
    if isinstance(value, bool):
        _raise_field_value_error(field_id, "an integer value")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        _raise_field_value_error(field_id, "an integer value")
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise _field_value_error(field_id, "an integer value") from exc
    _raise_field_value_error(field_id, "an integer value")


def _coerce_float(value: Any, field_id: str) -> float:
    if isinstance(value, bool):
        _raise_field_value_error(field_id, "a number value")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise _field_value_error(field_id, "a number value") from exc
    _raise_field_value_error(field_id, "a number value")


def _coerce_bool(value: Any, field_id: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    _raise_field_value_error(field_id, "a boolean value")


def _coerce_uuid(value: Any, field_id: str) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise _field_value_error(field_id, "a UUID value") from exc
    _raise_field_value_error(field_id, "a UUID value")


def _coerce_datetime(value: Any, field_id: str) -> datetime:
    if isinstance(value, datetime):
        normalized = normalize_utc(value)
        if normalized is None:
            _raise_field_value_error(field_id, "an ISO datetime or epoch value")
        return normalized
    if isinstance(value, (int, float)):
        return _epoch_to_datetime(float(value))
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            epoch_value = _parse_epoch(trimmed)
            if epoch_value is not None:
                return _epoch_to_datetime(epoch_value)
        try:
            normalized = normalize_utc(trimmed)
        except ValueError as exc:
            raise _field_value_error(field_id, "an ISO datetime or epoch value") from exc
        if normalized is None:
            _raise_field_value_error(field_id, "an ISO datetime or epoch value")
        return normalized
    _raise_field_value_error(field_id, "an ISO datetime or epoch value")


def _coerce_enum(value: Any, field: FilterField) -> Enum:
    enum_type = field.enum_type
    if enum_type is None:
        _raise_field_value_error(field.id, "a supported enum value")
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError as exc:
            raise _field_value_error(field.id, "a supported enum value") from exc
    _raise_field_value_error(field.id, "a supported enum value")


def _field_value_error(field_id: str, expected: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Filter '{field_id}' expects {expected}",
    )


def _raise_field_value_error(field_id: str, expected: str) -> Never:
    raise _field_value_error(field_id, expected)


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
