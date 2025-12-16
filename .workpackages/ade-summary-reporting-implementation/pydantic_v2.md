# Pydantic v2 models — `engine.run.completed` (Summary schema v1.0.0)

This document contains the strict Pydantic v2 models for the final contract used by `engine.run.completed`.

## Integration point

In `ade_engine/logging.py`, register the model:

```python
from ade_engine.summary_schema import RunCompletedSummaryV1

ENGINE_EVENT_SCHEMAS["engine.run.completed"] = RunCompletedSummaryV1
```

Then emit:

```python
logger.event(
    "run.completed",
    level=logging.INFO,
    message="Run completed summary",
    data=run_summary_dict_or_model_dump
)
```

> Note: `.event()` will validate payload using `model_validate(..., strict=True)`.

---

## Models (copy/paste)

```python
from __future__ import annotations

from typing import Any, Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]

SchemaVersion = Literal["1.0.0"]

ExecutionStatus = Literal["succeeded", "failed", "cancelled"]
EvaluationOutcome = Literal["success", "partial", "failure", "unknown"]
FindingSeverity = Literal["info", "warning", "error"]

MappingStatus = Literal["mapped", "ambiguous", "unmapped", "passthrough"]
MappingMethod = Literal["classifier", "patched", "passthrough"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -----------------------
# Common blocks
# -----------------------

class Failure(StrictModel):
    stage: str
    code: str
    message: str


class Execution(StrictModel):
    status: ExecutionStatus
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: NonNegativeFloat | None = None
    failure: Failure | None = None

    @model_validator(mode="after")
    def _failure_consistency(self) -> "Execution":
        if self.status == "succeeded" and self.failure is not None:
            raise ValueError("execution.failure must be null when status == 'succeeded'")
        if self.status != "succeeded" and self.failure is None:
            # allow missing failure only for 'cancelled' if you want; strict by default:
            raise ValueError("execution.failure must be provided when status != 'succeeded'")
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
    ambiguous: NonNegativeInt = 0

    @model_validator(mode="after")
    def _cols_ok(self) -> "ColumnsCount":
        if self.empty > self.total:
            raise ValueError("columns.empty must be <= columns.total")
        if self.mapped > self.total:
            raise ValueError("columns.mapped must be <= columns.total")
        if self.ambiguous > self.total:
            raise ValueError("columns.ambiguous must be <= columns.total")
        return self


class FieldsCount(StrictModel):
    expected: NonNegativeInt
    mapped: NonNegativeInt

    @model_validator(mode="after")
    def _fields_ok(self) -> "FieldsCount":
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
    # run-level includes workbooks; workbook-level includes sheets; sheet-level includes tables
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
    issues_by_severity: dict[str, NonNegativeInt] = Field(default_factory=dict)
    max_severity: str | None = None

    @model_validator(mode="after")
    def _issues_ok(self) -> "Validation":
        if sum(self.issues_by_severity.values()) != self.issues_total:
            raise ValueError("issues_total must equal sum(issues_by_severity)")
        if self.issues_total == 0 and self.max_severity is not None:
            raise ValueError("max_severity must be null when issues_total == 0")
        return self


class FieldOccurrences(StrictModel):
    tables: NonNegativeInt
    columns: NonNegativeInt


class FieldSummary(StrictModel):
    field: str
    label: str | None = None
    mapped: bool
    best_mapping_score: float | None = None
    occurrences: FieldOccurrences

    @model_validator(mode="after")
    def _field_ok(self) -> "FieldSummary":
        if self.mapped and self.best_mapping_score is None:
            raise ValueError("best_mapping_score must be set when mapped==true")
        if not self.mapped and self.best_mapping_score is not None:
            raise ValueError("best_mapping_score must be null when mapped==false")
        return self


class OutputsNormalized(StrictModel):
    path: str | None = None
    sheet_name: str | None = None
    range_a1: str | None = None


class Outputs(StrictModel):
    normalized: OutputsNormalized | None = None


# -----------------------
# Locator blocks
# -----------------------

class WorkbookRef(StrictModel):
    index: NonNegativeInt
    name: str


class SheetRef(StrictModel):
    index: NonNegativeInt
    name: str


class TableRef(StrictModel):
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
    row_start: NonNegativeInt
    row_count: NonNegativeInt = 1


class DataInfo(StrictModel):
    row_start: NonNegativeInt
    row_count: NonNegativeInt


class Candidate(StrictModel):
    field: str
    score: float


class Mapping(StrictModel):
    status: MappingStatus
    field: str | None = None
    score: float | None = None
    method: MappingMethod | None = None
    candidates: list[Candidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _mapping_ok(self) -> "Mapping":
        if self.status in ("mapped", "ambiguous"):
            if self.field is None or self.score is None or self.method is None:
                raise ValueError("mapped/ambiguous mapping must include field, score, and method")
        else:
            if self.field is not None or self.score is not None or self.method is not None:
                raise ValueError("unmapped/passthrough mapping must not include field/score/method")
        return self


class ColumnHeader(StrictModel):
    raw: str
    normalized: str


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
    def _columns_sorted(self) -> "TableStructure":
        # Enforce deterministic ordering for consumers.
        idxs = [c.index for c in self.columns]
        if idxs != sorted(idxs):
            raise ValueError("structure.columns must be sorted by index")
        return self


# -----------------------
# Summary nodes
# -----------------------

class TableSummary(StrictModel):
    scope: Literal["table"] = "table"
    locator: TableLocator
    execution: Execution
    evaluation: Evaluation
    counts: Counts
    validation: Validation
    fields: list[FieldSummary] = Field(default_factory=list)
    structure: TableStructure
    outputs: Outputs | None = None


class SheetScan(StrictModel):
    rows_emitted: NonNegativeInt
    stopped_early: bool
    truncated_rows: NonNegativeInt


class SheetSummary(StrictModel):
    scope: Literal["sheet"] = "sheet"
    locator: SheetLocator
    execution: Execution
    evaluation: Evaluation
    counts: Counts
    validation: Validation
    fields: list[FieldSummary] = Field(default_factory=list)
    scan: SheetScan | None = None
    tables: list[TableSummary] = Field(default_factory=list)
    outputs: Outputs | None = None


class WorkbookSummary(StrictModel):
    scope: Literal["workbook"] = "workbook"
    locator: WorkbookLocator
    execution: Execution
    evaluation: Evaluation
    counts: Counts
    validation: Validation
    fields: list[FieldSummary] = Field(default_factory=list)
    sheets: list[SheetSummary] = Field(default_factory=list)
    outputs: Outputs | None = None


class RunTiming(StrictModel):
    started_at: str
    completed_at: str
    duration_ms: NonNegativeFloat


class RunCompletedSummaryV1(StrictModel):
    schema_version: SchemaVersion = "1.0.0"
    scope: Literal["run"] = "run"

    execution: Execution
    evaluation: Evaluation
    counts: Counts
    validation: Validation
    fields: list[FieldSummary] = Field(default_factory=list)

    outputs: Outputs | None = None
    workbooks: list[WorkbookSummary] = Field(default_factory=list)

    @model_validator(mode="after")
    def _run_requires_timing(self) -> "RunCompletedSummaryV1":
        # For v1 we require timing in execution at run level.
        if self.execution.started_at is None or self.execution.completed_at is None:
            raise ValueError("run execution.started_at and execution.completed_at are required")
        if self.execution.duration_ms is None:
            raise ValueError("run execution.duration_ms is required")
        return self
```

---

## Notes for `ade_engine/logging.py` strict validation

- Because the engine’s `_validate_payload` calls `model_validate(payload, strict=True)`:
  - use plain `dict`, `list`, `str`, `int`, `float`, `bool`
  - avoid `Path` objects (convert to str)

- When you emit, prefer:

```python
payload = RunCompletedSummaryV1.model_validate(my_dict, strict=True).model_dump(mode="python", exclude_none=True)
logger.event("run.completed", data=payload)
```

This ensures you never emit invalid payloads.

