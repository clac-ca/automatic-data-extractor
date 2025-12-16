"""Event payload schemas and schema registry for ADE engine logging.

This module intentionally keeps payload models strict:
- ``extra="forbid"`` to prevent accidental schema drift
- runtime validation uses ``model_validate(..., strict=True)``
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENGINE_NAMESPACE = "engine"
CONFIG_NAMESPACE = "engine.config"

VALID_LOG_FORMATS = {"text", "ndjson", "json"}  # "json" is an alias for ndjson
DEFAULT_EVENT = "log"  # fallback event for plain log lines

PayloadModel: TypeAlias = type[BaseModel] | None


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -----------------------
# Schema v1 helpers
# -----------------------

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeFloat = Annotated[float, Field(ge=0)]

SchemaVersion = Literal[1]


class StrictPayloadV1(StrictModel):
    schema_version: SchemaVersion = 1


# -----------------------
# Simple engine event payloads (v1)
# -----------------------

class RunStartedPayloadV1(StrictPayloadV1):
    input_file: str | None
    config_package: str


class RunPlannedPayloadV1(StrictPayloadV1):
    output_file: str
    output_dir: str
    logs_file: str | None = None
    logs_dir: str | None = None


class WorkbookStartedPayloadV1(StrictPayloadV1):
    sheet_count: NonNegativeInt


class SheetStartedPayloadV1(StrictPayloadV1):
    sheet_name: str
    sheet_index: NonNegativeInt


class SheetTablesDetectedPayloadV1(StrictPayloadV1):
    sheet_name: str
    sheet_index: NonNegativeInt
    input_file: str
    row_count: NonNegativeInt
    table_count: NonNegativeInt
    tables: list[dict[str, Any]]


class TableDetectedPayloadV1(StrictPayloadV1):
    sheet_name: str
    sheet_index: NonNegativeInt
    table_index: NonNegativeInt
    input_file: str
    region: dict[str, Any]
    row_count: NonNegativeInt
    column_count: NonNegativeInt


class TableExtractedPayloadV1(StrictPayloadV1):
    sheet_name: str
    table_index: NonNegativeInt
    row_count: NonNegativeInt
    col_count: NonNegativeInt


class TableMappedPayloadV1(StrictPayloadV1):
    sheet_name: str
    table_index: NonNegativeInt
    mapped_fields: NonNegativeInt
    total_fields: NonNegativeInt
    passthrough_fields: NonNegativeInt


class TableMappingPatchedPayloadV1(StrictPayloadV1):
    sheet_name: str
    table_index: NonNegativeInt


class TableNormalizedPayloadV1(StrictPayloadV1):
    sheet_name: str
    table_index: NonNegativeInt
    row_count: NonNegativeInt
    issue_count: NonNegativeInt
    issues_by_severity: dict[str, NonNegativeInt]


class TableWrittenPayloadV1(StrictPayloadV1):
    sheet_name: str
    table_index: NonNegativeInt
    output_range: str


class DetectorResultV1(StrictModel):
    name: str
    scores: dict[str, float]
    duration_ms: float


class RowClassificationResultV1(StrictModel):
    row_kind: str
    score: float
    considered_row_kinds: list[str]


class ColumnClassificationResultV1(StrictModel):
    field: str
    score: float
    considered_fields: list[str]


class RowClassificationPayloadV1(StrictPayloadV1):
    sheet_name: str
    row_index: NonNegativeInt
    detectors: list[DetectorResultV1]
    scores: dict[str, float]
    classification: RowClassificationResultV1


class RowDetectorResultPayloadV1(StrictPayloadV1):
    sheet_name: str
    row_index: NonNegativeInt
    detector: DetectorResultV1


class ColumnDetectorResultPayloadV1(StrictPayloadV1):
    sheet_name: str
    column_index: NonNegativeInt
    detector: DetectorResultV1


class ColumnClassificationPayloadV1(StrictPayloadV1):
    sheet_name: str
    column_index: NonNegativeInt
    detectors: list[DetectorResultV1]
    scores: dict[str, float]
    classification: ColumnClassificationResultV1


# -----------------------
# Authoritative run summary (engine.run.completed) — schema v1
# -----------------------

ExecutionStatus = Literal["succeeded", "failed", "cancelled"]
EvaluationOutcome = Literal["success", "partial", "failure", "unknown"]
FindingSeverity = Literal["info", "warning", "error"]

MappingStatus = Literal["mapped", "ambiguous", "unmapped", "passthrough"]
MappingMethod = Literal["classifier", "rules", "patched"]


def _parse_iso8601(ts: str) -> str:
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("timestamp must be ISO-8601 (e.g. 2025-12-16T19:12:03Z)") from e
    return ts


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
        else:
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


class FieldOccurrences(StrictModel):
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


class Region(StrictModel):
    a1: str


class HeaderInfo(StrictModel):
    row_start: PositiveInt
    row_count: PositiveInt = 1
    inferred: bool = False


class DataInfo(StrictModel):
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
        if self.execution.started_at is None or self.execution.completed_at is None:
            raise ValueError("run execution.started_at and execution.completed_at are required")
        if self.execution.duration_ms is None:
            raise ValueError("run execution.duration_ms is required")

        idxs = [w.locator.workbook.index for w in self.workbooks]
        if idxs != sorted(idxs):
            raise ValueError("run.workbooks must be sorted by workbook.index")
        if len(set(idxs)) != len(idxs):
            raise ValueError("run.workbooks must not contain duplicate workbook.index")

        if self.counts.workbooks is not None and self.counts.workbooks != len(self.workbooks):
            raise ValueError("counts.workbooks must equal len(workbooks) for run scope when provided")

        _validate_fields_rollup(self.fields, self.counts, scope="run")
        return self


# Registry:
# - Missing key: unregistered (strict engine.* will error; others are open)
# - Value None: known-but-freeform payload (no validation)
# - Value BaseModel: validate + normalize payload through model
ENGINE_EVENT_SCHEMAS: dict[str, PayloadModel] = {
    f"{ENGINE_NAMESPACE}.{DEFAULT_EVENT}": None,
    f"{ENGINE_NAMESPACE}.run.started": RunStartedPayloadV1,
    f"{ENGINE_NAMESPACE}.run.planned": RunPlannedPayloadV1,
    f"{ENGINE_NAMESPACE}.run.completed": RunCompletedPayloadV1,
    f"{ENGINE_NAMESPACE}.workbook.started": WorkbookStartedPayloadV1,
    f"{ENGINE_NAMESPACE}.sheet.started": SheetStartedPayloadV1,
    f"{ENGINE_NAMESPACE}.sheet.tables_detected": SheetTablesDetectedPayloadV1,
    f"{ENGINE_NAMESPACE}.table.detected": TableDetectedPayloadV1,
    f"{ENGINE_NAMESPACE}.table.extracted": TableExtractedPayloadV1,
    f"{ENGINE_NAMESPACE}.table.mapped": TableMappedPayloadV1,
    f"{ENGINE_NAMESPACE}.table.mapping_patched": TableMappingPatchedPayloadV1,
    f"{ENGINE_NAMESPACE}.table.normalized": TableNormalizedPayloadV1,
    f"{ENGINE_NAMESPACE}.table.written": TableWrittenPayloadV1,
    # Debug/telemetry events (payloads are open/optional)
    f"{ENGINE_NAMESPACE}.settings.effective": None,
    # Detector results
    f"{ENGINE_NAMESPACE}.detector.row_result": RowDetectorResultPayloadV1,
    f"{ENGINE_NAMESPACE}.detector.column_result": ColumnDetectorResultPayloadV1,
    f"{ENGINE_NAMESPACE}.row_detector.summary": None,
    f"{ENGINE_NAMESPACE}.row_classification": RowClassificationPayloadV1,
    f"{ENGINE_NAMESPACE}.column_detector.candidate": None,
    f"{ENGINE_NAMESPACE}.column_detector.summary": None,
    f"{ENGINE_NAMESPACE}.column_classification": ColumnClassificationPayloadV1,
    # Transform/validation results
    f"{ENGINE_NAMESPACE}.transform.result": None,
    f"{ENGINE_NAMESPACE}.validation.result": None,
    f"{ENGINE_NAMESPACE}.transform.derived_merge": None,
    f"{ENGINE_NAMESPACE}.validation.summary": None,
    f"{ENGINE_NAMESPACE}.transform.overwrite": None,
    f"{ENGINE_NAMESPACE}.hook.start": None,
    f"{ENGINE_NAMESPACE}.hook.end": None,
}


__all__ = [
    "ENGINE_NAMESPACE",
    "CONFIG_NAMESPACE",
    "DEFAULT_EVENT",
    "VALID_LOG_FORMATS",
    "ENGINE_EVENT_SCHEMAS",
    "PayloadModel",
]
