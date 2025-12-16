"""Extension-facing contracts (contexts, enums, and table view)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

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


@dataclass(frozen=True)
class FieldDef:
    name: str
    label: str | None = None
    dtype: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RowDetectorContext:
    row_index: int
    row_values: Sequence[Any]
    sheet_name: str
    metadata: Mapping[str, Any]
    state: dict[str, Any]
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class TableView:
    """Read-only canonical table view for transforms/validators."""

    _columns: Mapping[str, list[Any]]
    mapping: Mapping[str, int | None]
    row_count: int

    def get(self, field: str) -> list[Any] | None:
        col = self._columns.get(field)
        if col is None:
            return None
        # Copy to prevent mutation of the underlying engine vectors.
        return list(col)

    def fields(self) -> list[str]:
        return list(self._columns.keys())


@dataclass(frozen=True)
class TransformContext:
    field_name: str
    column: list[Any]
    table: TableView
    mapping: Mapping[str, int | None]
    state: dict[str, Any]
    metadata: Mapping[str, Any]
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass(frozen=True)
class ValidateContext:
    field_name: str
    column: list[Any]
    table: TableView
    mapping: Mapping[str, int | None]
    state: dict[str, Any]
    metadata: Mapping[str, Any]
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass(frozen=True)
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
    "HookContext",
    "HookName",
    "RowKind",
    "RowDetectorContext",
    "ColumnDetectorContext",
    "TableView",
    "TransformContext",
    "ValidateContext",
]

