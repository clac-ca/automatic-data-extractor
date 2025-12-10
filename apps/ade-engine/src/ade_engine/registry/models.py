"""Core registry models and contexts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

ScorePatch = Mapping[str, float] | None


class RowKind(str, Enum):
    HEADER = "header"
    DATA = "data"
    UNKNOWN = "unknown"


class HookName(str, Enum):
    ON_WORKBOOK_START = "on_workbook_start"
    ON_SHEET_START = "on_sheet_start"
    ON_TABLE_DETECTED = "on_table_detected"
    ON_TABLE_MAPPED = "on_table_mapped"
    ON_TABLE_WRITTEN = "on_table_written"
    ON_WORKBOOK_BEFORE_SAVE = "on_workbook_before_save"


@dataclass
class FieldDef:
    name: str
    label: str | None = None
    required: bool = False
    dtype: str | None = None
    synonyms: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RowDetectorContext:
    row_index: int
    row_values: Sequence[Any]
    sheet_name: str
    metadata: Mapping[str, Any]
    state: dict[str, Any]
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass
class ColumnDetectorContext:
    column_index: int
    header: Any
    values: Sequence[Any]
    values_sample: Sequence[Any]
    sheet_name: str
    metadata: Mapping[str, Any]
    state: dict[str, Any]
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass
class TransformContext:
    field_name: str
    values: Sequence[Any]
    mapping: Mapping[str, int | None]
    state: dict[str, Any]
    metadata: Mapping[str, Any]
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass
class ValidateContext:
    field_name: str
    values: Sequence[Any]
    mapping: Mapping[str, int | None]
    state: dict[str, Any]
    metadata: Mapping[str, Any]
    column_index: int | None = None
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass
class HookContext:
    hook_name: HookName
    metadata: Mapping[str, Any]
    state: dict[str, Any]
    workbook: Any | None = None
    sheet: Any | None = None
    table: Any | None = None
    input_file_name: str | None = None
    logger: Any | None = None


__all__ = [
    "ScorePatch",
    "FieldDef",
    "HookName",
    "RowKind",
    "RowDetectorContext",
    "ColumnDetectorContext",
    "TransformContext",
    "ValidateContext",
    "HookContext",
]
