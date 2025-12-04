"""Hierarchical summary schemas for run/file/sheet/table scopes.

Notes on terminology:
- "mapped" always means "mapped at least once within this scope".
- "empty" rows/columns treat ``None`` or blank-string cells as empty values.
- Distinct headers are tracked by a normalized header string; physical column
  counts remain unnormalized.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SummaryScope = Literal["run", "file", "sheet", "table"]


class RowCounts(BaseModel):
    """Row-level counts."""

    total: int = 0
    empty: int = 0
    non_empty: int = 0

    model_config = ConfigDict(extra="forbid")


class ColumnCounts(BaseModel):
    """Column-level counts."""

    physical_total: int = 0
    physical_empty: int = 0
    physical_non_empty: int = 0
    distinct_headers: int = 0
    distinct_headers_mapped: int = 0
    distinct_headers_unmapped: int = 0

    model_config = ConfigDict(extra="forbid")


class FieldCounts(BaseModel):
    """Canonical field counts."""

    total: int = 0
    required: int = 0
    mapped: int = 0
    unmapped: int = 0
    required_mapped: int = 0
    required_unmapped: int = 0

    model_config = ConfigDict(extra="forbid")


class Counts(BaseModel):
    """Aggregate counts for a summary scope."""

    files: dict[str, int] | None = None
    sheets: dict[str, int] | None = None
    tables: dict[str, int] | None = None

    rows: RowCounts = Field(default_factory=RowCounts)
    columns: ColumnCounts = Field(default_factory=ColumnCounts)
    fields: FieldCounts = Field(default_factory=FieldCounts)

    model_config = ConfigDict(extra="forbid")


class FieldSummaryTable(BaseModel):
    """Field status at the table scope."""

    field: str
    label: str | None = None
    required: bool = False
    mapped: bool = False

    score: float | None = None
    source_column_index: int | None = None
    header: str | None = None

    model_config = ConfigDict(extra="forbid")


class FieldSummaryAggregate(BaseModel):
    """Field status at aggregate scopes (sheet/file/run)."""

    field: str
    label: str | None = None
    required: bool = False

    mapped: bool = False
    max_score: float | None = None

    tables_mapped: int | None = None
    sheets_mapped: int | None = None
    files_mapped: int | None = None

    model_config = ConfigDict(extra="forbid")


class ColumnSummaryTable(BaseModel):
    """Physical column status at table scope."""

    source_column_index: int
    header: str

    empty: bool
    non_empty_row_count: int

    mapped: bool
    mapped_field: str | None = None
    mapped_field_label: str | None = None
    score: float | None = None
    output_header: str | None = None

    model_config = ConfigDict(extra="forbid")


class ColumnSummaryDistinct(BaseModel):
    """Distinct header summary for aggregate scopes."""

    header: str
    header_normalized: str

    occurrences: dict[str, int] = Field(default_factory=dict)

    mapped: bool = False
    mapped_fields: list[str] = Field(default_factory=list)
    mapped_fields_counts: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ValidationSummary(BaseModel):
    """Validation counts for a summary scope."""

    rows_evaluated: int = 0
    issues_total: int = 0
    issues_by_severity: dict[str, int] = Field(default_factory=dict)
    issues_by_code: dict[str, int] = Field(default_factory=dict)
    issues_by_field: dict[str, int] = Field(default_factory=dict)
    max_severity: str | None = None

    model_config = ConfigDict(extra="forbid")


class BaseSummary(BaseModel):
    """Shared shape for run/file/sheet/table summaries."""

    schema_id: str = Field(default="ade.summary")
    schema_version: str = Field(default="1.0.0")
    scope: SummaryScope

    id: str
    parent_ids: dict[str, str] = Field(default_factory=dict)

    source: dict[str, Any] = Field(default_factory=dict)
    counts: Counts
    fields: list[FieldSummaryTable | FieldSummaryAggregate] = Field(default_factory=list)
    columns: list[ColumnSummaryTable | ColumnSummaryDistinct] = Field(default_factory=list)
    validation: ValidationSummary = Field(default_factory=ValidationSummary)
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class TableSummary(BaseSummary):
    """Table-level summary of a single normalized table."""

    scope: Literal["table"] = "table"
    fields: list[FieldSummaryTable] = Field(default_factory=list)
    columns: list[ColumnSummaryTable] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SheetSummary(BaseSummary):
    """Summary aggregated across tables within a sheet."""

    scope: Literal["sheet"] = "sheet"
    fields: list[FieldSummaryAggregate] = Field(default_factory=list)
    columns: list[ColumnSummaryDistinct] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class FileSummary(BaseSummary):
    """Summary aggregated across sheets within a file."""

    scope: Literal["file"] = "file"
    fields: list[FieldSummaryAggregate] = Field(default_factory=list)
    columns: list[ColumnSummaryDistinct] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RunSummary(BaseSummary):
    """Run-level summary aggregated across files within a run."""

    scope: Literal["run"] = "run"
    fields: list[FieldSummaryAggregate] = Field(default_factory=list)
    columns: list[ColumnSummaryDistinct] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "BaseSummary",
    "ColumnCounts",
    "ColumnSummaryDistinct",
    "ColumnSummaryTable",
    "Counts",
    "FieldCounts",
    "FieldSummaryAggregate",
    "FieldSummaryTable",
    "FileSummary",
    "RowCounts",
    "RunSummary",
    "SheetSummary",
    "SummaryScope",
    "TableSummary",
    "ValidationSummary",
]
