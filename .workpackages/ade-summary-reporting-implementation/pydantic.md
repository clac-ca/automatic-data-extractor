# Pydantic v2 models — `engine.run.completed` (schema v1)

This document contains **strict** Pydantic v2 models for the `engine.run.completed` event payload.

Design goals:

- **Strict, stable contract** (`extra="forbid"` + `strict=True`)
- **Deterministic ordering** for child arrays (workbooks → sheets → tables → columns)
- **Practical payload size** (detailed mapping only at table scope; field rollups at run/workbook/sheet)

---

## Integration

### Schema registry

Define the model(s) and register them under the fully-qualified event name:

```python
# ade_engine/models/events.py

ENGINE_EVENT_SCHEMAS: dict[str, type[BaseModel]] = {}

ENGINE_EVENT_SCHEMAS["engine.run.completed"] = RunCompletedPayloadV1
```

### Emitting the event

In engine logger context, emit the unqualified name (the engine logger qualifies it):

```python
logger.event(
    "run.completed",  # engine logger qualifies to "engine.run.completed"
    level=logging.INFO,
    message="Run completed summary",
    data=payload,
)
```

If emitting outside engine logger context, emit the fully-qualified name:

```python
logger.event("engine.run.completed", level=logging.INFO, data=payload)
```

> Note: `.event()` validates payloads using `model_validate(..., strict=True)`.

---

## Emission guidance (recommended)

Emit only JSON-friendly primitives and keep payloads compact:

```python
payload = RunCompletedPayloadV1.model_validate(my_dict, strict=True).model_dump(
    mode="python",
    exclude_none=True,
)

logger.event("run.completed", level=logging.INFO, data=payload)
```

This ensures invalid payloads are rejected *before* emission.

---

## Models (copy/paste)

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# -----------------------
# Scalar helpers
# -----------------------

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeFloat = Annotated[float, Field(ge=0)]

SchemaVersion = Literal[1]

ExecutionStatus = Literal["succeeded", "failed", "cancelled"]
EvaluationOutcome = Literal["success", "partial", "failure", "unknown"]
FindingSeverity = Literal["info", "warning", "error"]

MappingStatus = Literal["mapped", "ambiguous", "unmapped", "passthrough"]

# Intentionally small v1 enum; add values only via schema bump.
MappingMethod = Literal["classifier", "rules", "patched"]


def _parse_iso8601(ts: str) -> str:
    """Validate ISO-8601 timestamps without coercing types.

    Accepts common forms like:
    - 2025-12-16T19:12:03Z
    - 2025-12-16T19:12:03+00:00
    """
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("timestamp must be ISO-8601 (e.g. 2025-12-16T19:12:03Z)") from e
    return ts


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StrictPayloadV1(StrictModel):
    schema_version: SchemaVersion = 1


# -----------------------
# Run scope blocks
# -----------------------

class Failure(StrictModel):
    stage: str
    code: str
    message: str


class Execution(StrictModel):
    status: ExecutionStatus
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: NonNegativeInt | None = None
    failure: Failure | None = None

    _started_at_fmt = field_validator("started_at")(lambda v: _parse_iso8601(v) if v is not None else v)
    _completed_at_fmt = field_validator("completed_at")(lambda v: _parse_iso8601(v) if v is not None else v)

    @model_validator(mode="after")
    def _failure_consistency(self) -> "Execution":
        if self.status == "succeeded":
            if self.failure is not None:
                raise ValueError("execution.failure must be null when status == 'succeeded'")
        elif self.status == "failed":
            if self.failure is None:
                raise ValueError("execution.failure must be provided when status == 'failed'")
        else:  # cancelled
            # Cancellation may be user-initiated; failure details are optional.
            pass
        return self


class Finding(StrictModel):
    code: str
    severity: FindingSeverity
    message: str
    count: NonNegativeInt | None = None
    meta: dict[str, Any] | None = None


class Evaluation(StrictModel):
    outcome: EvaluationOutcome
    findings: list[Finding] = Field(default_factory=list)


# -----------------------
# Rollup blocks
# -----------------------

class RowsCount(StrictModel):
    total: NonNegativeInt
    empty: NonNegativeInt

    @model_validator(mode="after")
    def _rows_ok(self) -> "RowsCount":
        if self.empty > self.total:
            raise ValueError("rows.empty must be <= rows.total")
        return self


class ColumnsCount(StrictModel):
    total: NonNegativeInt
    empty: NonNegativeInt

    mapped: NonNegativeInt
    ambiguous: NonNegativeInt
    unmapped: NonNegativeInt
    passthrough: NonNegativeInt

    @model_validator(mode="after")
    def _cols_ok(self) -> "ColumnsCount":
        if self.empty > self.total:
            raise ValueError("columns.empty must be <= columns.total")

        # Mapping-status buckets partition ALL columns.
        if any(x > self.total for x in (self.mapped, self.ambiguous, self.unmapped, self.passthrough)):
            raise ValueError("column mapping counts must be <= columns.total")

        if (self.mapped + self.ambiguous + self.unmapped + self.passthrough) != self.total:
            raise ValueError("columns.(mapped+ambiguous+unmapped+passthrough) must equal columns.total")

        return self


class FieldsCount(StrictModel):
    expected: NonNegativeInt
    mapped: NonNegativeInt

    @model_validator(mode="after")
    def _fields_ok(self) -> "FieldsCount":
        # v1 semantics: number of expected fields mapped at least once in this scope.
        if self.mapped > self.expected:
            raise ValueError("fields.mapped must be <= fields.expected")
        return self


class CellsCount(StrictModel):
    total: NonNegativeInt
    non_empty: NonNegativeInt

    @model_validator(mode="after")
    def _cells_ok(self) -> "CellsCount":
        if self.non_empty > self.total:
            raise ValueError("cells.non_empty must be <= cells.total")
        return self


class Counts(StrictModel):
    # Run-level includes workbooks; workbook-level includes sheets; sheet-level includes tables.
    workbooks: NonNegativeInt | None = None
    sheets: NonNegativeInt | None = None
    tables: NonNegativeInt | None = None

    rows: RowsCount
    columns: ColumnsCount
    fields: FieldsCount
    cells: CellsCount | None = None


class Validation(StrictModel):
    rows_evaluated: NonNegativeInt
    issues_total: NonNegativeInt
    issues_by_severity: dict[FindingSeverity, NonNegativeInt] = Field(default_factory=dict)
    max_severity: FindingSeverity | None = None

    @model_validator(mode="after")
    def _issues_ok(self) -> "Validation":
        if sum(self.issues_by_severity.values()) != self.issues_total:
            raise ValueError("issues_total must equal sum(issues_by_severity)")

        if self.issues_total == 0:
            if self.max_severity is not None:
                raise ValueError("max_severity must be null when issues_total == 0")
        else:
            if self.max_severity is None:
                raise ValueError("max_severity must be set when issues_total > 0")

        return self


# -----------------------
# Field coverage rollups (derived)
# -----------------------

class FieldOccurrences(StrictModel):
    # tables: number of distinct tables where this field appears at least once
    # columns: total physical columns mapped to this field (across all tables)
    tables: NonNegativeInt
    columns: NonNegativeInt


class FieldSummary(StrictModel):
    field: str
    label: str | None = None
    mapped: bool
    best_mapping_score: NonNegativeFloat | None = None
    occurrences: FieldOccurrences

    @model_validator(mode="after")
    def _field_ok(self) -> "FieldSummary":
        if self.mapped and self.best_mapping_score is None:
            raise ValueError("best_mapping_score must be set when mapped==true")
        if not self.mapped and self.best_mapping_score is not None:
            raise ValueError("best_mapping_score must be null when mapped==false")
        return self


def _validate_fields_rollup(fields: list[FieldSummary], counts: Counts, *, scope: str) -> None:
    """Validate optional field rollups for consistency.

    When provided, fields[] should contain exactly one entry per expected field,
    and counts.fields.mapped should match the number of mapped==true entries.
    """
    if not fields:
        return

    names = [f.field for f in fields]
    if len(set(names)) != len(names):
        raise ValueError(f"{scope}.fields must not contain duplicate field values")

    if len(fields) != counts.fields.expected:
        raise ValueError(f"{scope}.fields must contain exactly counts.fields.expected entries when provided")

    mapped = sum(1 for f in fields if f.mapped)
    if mapped != counts.fields.mapped:
        raise ValueError(f"{scope}.counts.fields.mapped must equal number of fields with mapped==true")


# -----------------------
# Outputs pointers
# -----------------------

class OutputsNormalized(StrictModel):
    path: str | None = None
    sheet_name: str | None = None
    range_a1: str | None = None

    @model_validator(mode="after")
    def _normalized_ok(self) -> "OutputsNormalized":
        if (self.sheet_name is not None or self.range_a1 is not None) and self.path is None:
            raise ValueError("outputs.normalized.path is required when sheet_name or range_a1 is set")
        return self


class Outputs(StrictModel):
    normalized: OutputsNormalized | None = None


# -----------------------
# Locator blocks
# -----------------------

class WorkbookRef(StrictModel):
    # 0-based index into the list of input workbooks
    index: NonNegativeInt
    name: str


class SheetRef(StrictModel):
    # 0-based index into the workbook's sheets
    index: NonNegativeInt
    name: str


class TableRef(StrictModel):
    # 0-based index into the detected tables within the sheet
    index: NonNegativeInt


class WorkbookLocator(StrictModel):
    workbook: WorkbookRef


class SheetLocator(StrictModel):
    workbook: WorkbookRef
    sheet: SheetRef


class TableLocator(StrictModel):
    workbook: WorkbookRef
    sheet: SheetRef
    table: TableRef


# -----------------------
# Table structure blocks
# -----------------------

class Region(StrictModel):
    a1: str


class HeaderInfo(StrictModel):
    # Spreadsheet-style row numbers (1-based)
    row_start: PositiveInt
    row_count: PositiveInt = 1
    inferred: bool = False


class DataInfo(StrictModel):
    # Spreadsheet-style row numbers (1-based)
    row_start: PositiveInt
    row_count: NonNegativeInt


class Candidate(StrictModel):
    field: str
    score: NonNegativeFloat


UnmappedReason = Literal[
    "no_signal",
    "below_threshold",
    "ambiguous_top_candidates",
    "duplicate_field",
    "empty_or_placeholder_header",
    "passthrough_policy",
]

MAX_CANDIDATES = 3


class Mapping(StrictModel):
    status: MappingStatus
    field: str | None = None
    score: NonNegativeFloat | None = None
    method: MappingMethod | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    unmapped_reason: UnmappedReason | None = None

    @model_validator(mode="after")
    def _mapping_ok(self) -> "Mapping":
        if len(self.candidates) > MAX_CANDIDATES:
            raise ValueError(f"mapping.candidates must be <= {MAX_CANDIDATES}")

        scores = [c.score for c in self.candidates]
        if scores != sorted(scores, reverse=True):
            raise ValueError("mapping.candidates must be sorted by descending score")

        fields = [c.field for c in self.candidates]
        if len(set(fields)) != len(fields):
            raise ValueError("mapping.candidates must not contain duplicate fields")

        if self.status == "mapped":
            if self.field is None or self.score is None or self.method is None:
                raise ValueError("mapped mapping must include field, score, and method")
            if self.unmapped_reason is not None:
                raise ValueError("unmapped_reason must be null when status == 'mapped'")

        elif self.status == "ambiguous":
            if self.field is not None or self.score is not None or self.method is not None:
                raise ValueError("ambiguous mapping must not include field/score/method")
            if not self.candidates:
                raise ValueError("ambiguous mapping must include candidates")
            if self.unmapped_reason is None:
                raise ValueError("unmapped_reason must be provided when status == 'ambiguous'")

        elif self.status == "unmapped":
            if self.field is not None or self.score is not None or self.method is not None:
                raise ValueError("unmapped mapping must not include field/score/method")
            if self.unmapped_reason is None:
                raise ValueError("unmapped_reason must be provided when status == 'unmapped'")

        else:  # passthrough
            if self.field is not None or self.score is not None or self.method is not None:
                raise ValueError("passthrough mapping must not include field/score/method")
            if self.unmapped_reason != "passthrough_policy":
                raise ValueError("passthrough mapping must set unmapped_reason == 'passthrough_policy'")

        return self


class ColumnHeader(StrictModel):
    raw: str | None
    normalized: str | None

    @model_validator(mode="after")
    def _header_ok(self) -> "ColumnHeader":
        if (self.raw is None) != (self.normalized is None):
            raise ValueError("header.raw and header.normalized must both be null or both be set")
        return self


class ColumnStructure(StrictModel):
    index: NonNegativeInt
    header: ColumnHeader
    non_empty_cells: NonNegativeInt
    mapping: Mapping


class TableStructure(StrictModel):
    region: Region
    header: HeaderInfo
    data: DataInfo
    columns: list[ColumnStructure] = Field(default_factory=list)

    @model_validator(mode="after")
    def _columns_sorted_unique(self) -> "TableStructure":
        idxs = [c.index for c in self.columns]
        if idxs != sorted(idxs):
            raise ValueError("structure.columns must be sorted by index")
        if len(set(idxs)) != len(idxs):
            raise ValueError("structure.columns must not contain duplicate index values")
        return self


# -----------------------
# Summary nodes
# -----------------------

class TableSummary(StrictModel):
    scope: Literal["table"] = "table"
    locator: TableLocator
    counts: Counts
    validation: Validation
    structure: TableStructure
    outputs: Outputs | None = None


class SheetScan(StrictModel):
    rows_emitted: NonNegativeInt
    stopped_early: bool
    truncated_rows: NonNegativeInt

    @model_validator(mode="after")
    def _scan_ok(self) -> "SheetScan":
        if not self.stopped_early and self.truncated_rows != 0:
            raise ValueError("scan.truncated_rows must be 0 when stopped_early == false")
        return self


class SheetSummary(StrictModel):
    scope: Literal["sheet"] = "sheet"
    locator: SheetLocator
    counts: Counts
    validation: Validation
    fields: list[FieldSummary] = Field(default_factory=list)
    scan: SheetScan | None = None
    tables: list[TableSummary] = Field(default_factory=list)

    @model_validator(mode="after")
    def _tables_sorted(self) -> "SheetSummary":
        idxs = [t.locator.table.index for t in self.tables]
        if idxs != sorted(idxs):
            raise ValueError("sheet.tables must be sorted by table.index")
        if len(set(idxs)) != len(idxs):
            raise ValueError("sheet.tables must not contain duplicate table.index")
        if self.counts.tables is not None and self.counts.tables != len(self.tables):
            raise ValueError("counts.tables must equal len(tables) for sheet scope when provided")

        _validate_fields_rollup(self.fields, self.counts, scope="sheet")
        return self


class WorkbookSummary(StrictModel):
    scope: Literal["workbook"] = "workbook"
    locator: WorkbookLocator
    counts: Counts
    validation: Validation
    fields: list[FieldSummary] = Field(default_factory=list)
    sheets: list[SheetSummary] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sheets_sorted(self) -> "WorkbookSummary":
        idxs = [s.locator.sheet.index for s in self.sheets]
        if idxs != sorted(idxs):
            raise ValueError("workbook.sheets must be sorted by sheet.index")
        if len(set(idxs)) != len(idxs):
            raise ValueError("workbook.sheets must not contain duplicate sheet.index")
        if self.counts.sheets is not None and self.counts.sheets != len(self.sheets):
            raise ValueError("counts.sheets must equal len(sheets) for workbook scope when provided")

        _validate_fields_rollup(self.fields, self.counts, scope="workbook")
        return self


class RunCompletedPayloadV1(StrictPayloadV1):
    scope: Literal["run"] = "run"

    execution: Execution
    evaluation: Evaluation
    counts: Counts
    validation: Validation
    fields: list[FieldSummary] = Field(default_factory=list)

    outputs: Outputs | None = None
    workbooks: list[WorkbookSummary] = Field(default_factory=list)

    @model_validator(mode="after")
    def _run_invariants(self) -> "RunCompletedPayloadV1":
        # v1 requires timing at run scope.
        if self.execution.started_at is None or self.execution.completed_at is None:
            raise ValueError("run execution.started_at and execution.completed_at are required")
        if self.execution.duration_ms is None:
            raise ValueError("run execution.duration_ms is required")

        # Deterministic ordering for consumers.
        idxs = [w.locator.workbook.index for w in self.workbooks]
        if idxs != sorted(idxs):
            raise ValueError("run.workbooks must be sorted by workbook.index")
        if len(set(idxs)) != len(idxs):
            raise ValueError("run.workbooks must not contain duplicate workbook.index")

        if self.counts.workbooks is not None and self.counts.workbooks != len(self.workbooks):
            raise ValueError("counts.workbooks must equal len(workbooks) for run scope when provided")

        _validate_fields_rollup(self.fields, self.counts, scope="run")
        return self
```

---

## Notes

- Workbook/sheet/table indexes are **0-based**.
- `structure.header.row_start` and `structure.data.row_start` are **1-based** (spreadsheet-style).
- `counts.fields.mapped` is **de-duplicated** within the scope (an expected field counted once even if it appears in multiple tables).
- `fields[]` is a **derived rollup** and may appear at run/workbook/sheet scopes for convenience (table scope remains the ground truth).
