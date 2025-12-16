"""
Pydantic v2 models for the `engine.run.completed` summary payload.

Contract goals:
- Strict, intentionally structured (extra="forbid")
- Consistent hierarchy: run → workbook → sheets → tables
- Metrics-friendly counts, plus human-friendly structure/mapping detail
- Works with your existing logging pipeline:
    _validate_payload(...): model_validate(payload, strict=True)
    model_dump(mode="python", exclude_none=True)

NOTE:
- Timestamps are strings (RFC3339 UTC) to match current logging behavior.
- All counts are non-negative and include invariants (e.g. empty + non_empty == total).
"""

from __future__ import annotations

from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ----------------------------
# Shared / base definitions
# ----------------------------

NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


class StrictPayload(BaseModel):
    """Strict payload base: forbids unknown fields to keep schemas stable."""
    model_config = ConfigDict(extra="forbid")


# ----------------------------
# Run-level
# ----------------------------

RunStatus = Literal["succeeded", "failed"]


class RunInputSummary(StrictPayload):
    file: str
    sheets_requested: list[str]


class RunOutputSummary(StrictPayload):
    file: str | None = None
    log_file: str | None = None


class RunErrorSummary(StrictPayload):
    """
    Error detail for failed runs (or partial failures if you introduce that later).
    Keep this minimal and stable; avoid dumping huge objects.
    """
    type: str
    message: str
    stack_trace: str | None = None
    stage: str | None = None


class RunSummary(StrictPayload):
    status: RunStatus
    started_at: str  # RFC3339 UTC
    completed_at: str  # RFC3339 UTC
    duration_ms: NonNegativeFloat

    input: RunInputSummary
    output: RunOutputSummary
    error: RunErrorSummary | None = None


# ----------------------------
# Counts (consistent at workbook/sheet/table)
# ----------------------------

class TotalCount(StrictPayload):
    total: NonNegativeInt


class RowCounts(StrictPayload):
    total: NonNegativeInt
    empty: NonNegativeInt
    non_empty: NonNegativeInt

    @model_validator(mode="after")
    def _check_invariants(self) -> "RowCounts":
        if self.empty + self.non_empty != self.total:
            raise ValueError("rows invariant violated: empty + non_empty must equal total")
        return self


class ColumnCounts(StrictPayload):
    """
    Counts for *physical* columns at this scope.
    - empty/non_empty partition total (a column is empty if all cells are empty)
    - mapped/unmapped partition total (mapped means ADE assigned a field)
    """
    total: NonNegativeInt
    empty: NonNegativeInt
    non_empty: NonNegativeInt
    mapped: NonNegativeInt
    unmapped: NonNegativeInt

    @model_validator(mode="after")
    def _check_invariants(self) -> "ColumnCounts":
        if self.empty + self.non_empty != self.total:
            raise ValueError("columns invariant violated: empty + non_empty must equal total")
        if self.mapped + self.unmapped != self.total:
            raise ValueError("columns invariant violated: mapped + unmapped must equal total")
        return self


class FieldCounts(StrictPayload):
    """
    Field counts for this scope.
    `derived` are fields produced by transforms (if/when you add those),
    counted as their own bucket for analysis.
    """
    total: NonNegativeInt
    mapped: NonNegativeInt
    unmapped: NonNegativeInt
    derived: NonNegativeInt

    @model_validator(mode="after")
    def _check_invariants(self) -> "FieldCounts":
        if self.mapped + self.unmapped + self.derived != self.total:
            raise ValueError("fields invariant violated: mapped + unmapped + derived must equal total")
        return self


class SummaryCounts(StrictPayload):
    """
    This exact shape is reused at workbook, sheet, and table level.
    """
    sheets: TotalCount
    tables: TotalCount
    rows: RowCounts
    columns: ColumnCounts
    fields: FieldCounts


# ----------------------------
# Validation (consistent at workbook/sheet/table)
# ----------------------------

class ValidationSummary(StrictPayload):
    issues_total: NonNegativeInt
    issues_by_severity: dict[str, NonNegativeInt] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_invariants(self) -> "ValidationSummary":
        if sum(self.issues_by_severity.values()) != self.issues_total:
            raise ValueError("validation invariant violated: sum(issues_by_severity) must equal issues_total")
        return self


# ----------------------------
# Workbook-level rollups
# ----------------------------

class FieldRollupSummary(StrictPayload):
    """
    Workbook-level rollup for registry fields.
    """
    field: str
    tables_mapped: NonNegativeInt
    max_score: float | None = None


# ----------------------------
# Sheet-level
# ----------------------------

class SheetScanSummary(StrictPayload):
    """
    Captures how ADE handled sparse/empty data *during sheet materialization*.
    """
    rows_emitted: NonNegativeInt
    stopped_early: bool
    truncated_rows: NonNegativeInt


# ----------------------------
# Table-level structure + mapping
# ----------------------------

class TableRegionSummary(StrictPayload):
    """
    ADE's belief about table boundary/structure (indices are 0-based).
    """
    header_row_index: NonNegativeInt
    data_start_row_index: NonNegativeInt
    data_end_row_index: NonNegativeInt
    header_inferred: bool

    @model_validator(mode="after")
    def _check_invariants(self) -> "TableRegionSummary":
        if self.data_start_row_index < self.header_row_index:
            raise ValueError("table region invalid: data_start_row_index must be >= header_row_index")
        if self.data_end_row_index < self.data_start_row_index:
            raise ValueError("table region invalid: data_end_row_index must be >= data_start_row_index")
        return self


class TableShapeSummary(StrictPayload):
    rows: NonNegativeInt
    columns: NonNegativeInt


class FieldCandidateSummary(StrictPayload):
    field: str
    score: float


class ColumnValuesSummary(StrictPayload):
    non_empty: NonNegativeInt
    empty: NonNegativeInt

    @model_validator(mode="after")
    def _check_invariants(self) -> "ColumnValuesSummary":
        # total is intentionally not stored here; table/column totals are elsewhere
        return self


class ColumnMappingSummary(StrictPayload):
    """
    Column → field decision, including alternatives for debugging/analysis.
    If a column is unmapped, `field` and `score` should be null and `reason_unmapped` should be set.
    """
    field: str | None = None
    score: float | None = None
    candidates: list[FieldCandidateSummary] = Field(default_factory=list)
    reason_unmapped: str | None = None

    @model_validator(mode="after")
    def _check_invariants(self) -> "ColumnMappingSummary":
        if self.field is None:
            if self.reason_unmapped is None:
                raise ValueError("unmapped column must provide reason_unmapped")
        else:
            if self.score is None:
                raise ValueError("mapped column must provide score")
        return self


class ColumnSummary(StrictPayload):
    column_index: NonNegativeInt
    header: str
    header_normalized: str
    values: ColumnValuesSummary
    mapping: ColumnMappingSummary


class MappedFieldSummary(StrictPayload):
    field: str
    source_column_index: NonNegativeInt
    source_header: str
    score: float


class TableFieldsSummary(StrictPayload):
    mapped: list[MappedFieldSummary] = Field(default_factory=list)

    # You haven't locked a derived-field structure yet; keep it open-but-structured:
    # "list of objects", but object keys are not constrained at this time.
    derived: list[dict[str, Any]] = Field(default_factory=list)

    unmapped: list[str] = Field(default_factory=list)


class TableOutputSummary(StrictPayload):
    range: str  # e.g. "A1:AV129"


class TableSummary(StrictPayload):
    table_index: NonNegativeInt

    region: TableRegionSummary
    shape: TableShapeSummary

    counts: SummaryCounts
    fields: TableFieldsSummary
    columns: list[ColumnSummary] = Field(default_factory=list)

    validation: ValidationSummary
    output: TableOutputSummary

    @model_validator(mode="after")
    def _check_consistency(self) -> "TableSummary":
        # Shape ↔ counts consistency
        if self.shape.rows != self.counts.rows.total:
            raise ValueError("table inconsistency: shape.rows must equal counts.rows.total")
        if self.shape.columns != self.counts.columns.total:
            raise ValueError("table inconsistency: shape.columns must equal counts.columns.total")
        return self


class SheetSummary(StrictPayload):
    sheet_name: str
    sheet_index: NonNegativeInt

    scan: SheetScanSummary
    counts: SummaryCounts
    validation: ValidationSummary

    tables: list[TableSummary] = Field(default_factory=list)


class WorkbookSummary(StrictPayload):
    counts: SummaryCounts
    validation: ValidationSummary

    fields: list[FieldRollupSummary] = Field(default_factory=list)
    sheets: list[SheetSummary] = Field(default_factory=list)


# ----------------------------
# Top-level payload
# ----------------------------

class RunCompletedPayload(StrictPayload):
    schema_version: str  # e.g. "1.0.0"
    run: RunSummary
    workbook: WorkbookSummary
