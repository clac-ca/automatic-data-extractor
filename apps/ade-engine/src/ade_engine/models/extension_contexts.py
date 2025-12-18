"""Extension-facing contracts (contexts, enums, and table view)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

import polars as pl

from ade_engine.models.table import TableRegion

ScorePatch = Mapping[str, float] | None


class RowKind(str, Enum):
    HEADER = "header"
    DATA = "data"
    UNKNOWN = "unknown"


class HookName(str, Enum):
    ON_WORKBOOK_START = "on_workbook_start"
    ON_SHEET_START = "on_sheet_start"
    ON_TABLE_MAPPED = "on_table_mapped"
    ON_TABLE_TRANSFORMED = "on_table_transformed"
    ON_TABLE_VALIDATED = "on_table_validated"
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
    settings: Any
    metadata: Mapping[str, Any]
    state: dict[str, Any]
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass(frozen=True)
class ColumnDetectorContext:
    table: pl.DataFrame
    column: pl.Series
    column_sample: Sequence[str]
    column_name: str
    column_index: int
    header_text: str
    settings: Any
    sheet_name: str
    metadata: Mapping[str, Any]
    state: dict[str, Any]
    table_region: TableRegion | None = None
    table_index: int | None = None
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass(frozen=True)
class TransformContext:
    field_name: str
    table: pl.DataFrame
    settings: Any
    state: dict[str, Any]
    metadata: Mapping[str, Any]
    table_region: TableRegion | None = None
    table_index: int | None = None
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass(frozen=True)
class ValidateContext:
    field_name: str
    table: pl.DataFrame
    settings: Any
    state: dict[str, Any]
    metadata: Mapping[str, Any]
    table_region: TableRegion | None = None
    table_index: int | None = None
    input_file_name: str | None = None
    logger: Any | None = None


@dataclass(frozen=True)
class HookContext:
    settings: Any
    metadata: Mapping[str, Any]
    state: dict[str, Any]
    workbook: Any | None = None
    sheet: Any | None = None
    table: pl.DataFrame | None = None
    table_region: TableRegion | None = None
    table_index: int | None = None
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
    "TransformContext",
    "ValidateContext",
]
