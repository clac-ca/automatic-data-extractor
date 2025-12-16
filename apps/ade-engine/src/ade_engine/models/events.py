"""Event payload schemas and schema registry for ADE engine logging."""

from __future__ import annotations

from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict

ENGINE_NAMESPACE = "engine"
CONFIG_NAMESPACE = "engine.config"

VALID_LOG_FORMATS = {"text", "ndjson", "json"}  # "json" is an alias for ndjson
DEFAULT_EVENT = "log"  # fallback event for plain log lines

PayloadModel: TypeAlias = type[BaseModel] | None


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunStartedPayload(StrictPayload):
    input_file: str | None
    config_package: str


class RunPlannedPayload(StrictPayload):
    output_file: str
    output_dir: str
    logs_file: str | None = None
    logs_dir: str | None = None


class WorkbookStartedPayload(StrictPayload):
    sheet_count: int


class SheetStartedPayload(StrictPayload):
    sheet_name: str
    sheet_index: int


class SheetTablesDetectedPayload(StrictPayload):
    sheet_name: str
    sheet_index: int
    input_file: str
    row_count: int
    table_count: int
    tables: list[dict[str, Any]]


class TableDetectedPayload(StrictPayload):
    sheet_name: str
    sheet_index: int
    table_index: int
    input_file: str
    region: dict[str, Any]
    row_count: int
    column_count: int


class TableExtractedPayload(StrictPayload):
    sheet_name: str
    table_index: int
    row_count: int
    col_count: int


class TableMappedPayload(StrictPayload):
    sheet_name: str
    table_index: int
    mapped_fields: int
    total_fields: int
    passthrough_fields: int


class TableMappingPatchedPayload(StrictPayload):
    sheet_name: str
    table_index: int


class TableNormalizedPayload(StrictPayload):
    sheet_name: str
    table_index: int
    row_count: int
    issue_count: int
    issues_by_severity: dict[str, int]


class TableWrittenPayload(StrictPayload):
    sheet_name: str
    table_index: int
    output_range: str


class DetectorResult(StrictPayload):
    name: str
    scores: dict[str, float]
    duration_ms: float


class RowClassificationResult(StrictPayload):
    row_kind: str
    score: float
    considered_row_kinds: list[str]


class ColumnClassificationResult(StrictPayload):
    field: str
    score: float
    considered_fields: list[str]


class RowClassificationPayload(StrictPayload):
    sheet_name: str
    row_index: int
    detectors: list[DetectorResult]
    scores: dict[str, float]
    classification: RowClassificationResult


class RowDetectorResultPayload(StrictPayload):
    sheet_name: str
    row_index: int
    detector: DetectorResult


class ColumnDetectorResultPayload(StrictPayload):
    sheet_name: str
    column_index: int
    detector: DetectorResult


class ColumnClassificationPayload(StrictPayload):
    sheet_name: str
    column_index: int
    detectors: list[DetectorResult]
    scores: dict[str, float]
    classification: ColumnClassificationResult


class RunCompletedPayload(StrictPayload):
    status: str
    started_at: str
    completed_at: str
    stage: str | None = None
    output_path: str | None = None
    error: dict[str, Any] | None = None


# Registry:
# - Missing key: unregistered (strict engine.* will error; others are open)
# - Value None: known-but-freeform payload (no validation)
# - Value BaseModel: validate + normalize payload through model
ENGINE_EVENT_SCHEMAS: dict[str, PayloadModel] = {
    f"{ENGINE_NAMESPACE}.{DEFAULT_EVENT}": None,
    f"{ENGINE_NAMESPACE}.run.started": RunStartedPayload,
    f"{ENGINE_NAMESPACE}.run.planned": RunPlannedPayload,
    f"{ENGINE_NAMESPACE}.run.completed": RunCompletedPayload,
    f"{ENGINE_NAMESPACE}.workbook.started": WorkbookStartedPayload,
    f"{ENGINE_NAMESPACE}.sheet.started": SheetStartedPayload,
    f"{ENGINE_NAMESPACE}.sheet.tables_detected": SheetTablesDetectedPayload,
    f"{ENGINE_NAMESPACE}.table.detected": TableDetectedPayload,
    f"{ENGINE_NAMESPACE}.table.extracted": TableExtractedPayload,
    f"{ENGINE_NAMESPACE}.table.mapped": TableMappedPayload,
    f"{ENGINE_NAMESPACE}.table.mapping_patched": TableMappingPatchedPayload,
    f"{ENGINE_NAMESPACE}.table.normalized": TableNormalizedPayload,
    f"{ENGINE_NAMESPACE}.table.written": TableWrittenPayload,
    # Debug/telemetry events (payloads are open/optional)
    f"{ENGINE_NAMESPACE}.settings.effective": None,
    # Detector results
    f"{ENGINE_NAMESPACE}.detector.row_result": RowDetectorResultPayload,
    f"{ENGINE_NAMESPACE}.detector.column_result": ColumnDetectorResultPayload,
    f"{ENGINE_NAMESPACE}.row_detector.summary": None,
    f"{ENGINE_NAMESPACE}.row_classification": RowClassificationPayload,
    f"{ENGINE_NAMESPACE}.column_detector.candidate": None,
    f"{ENGINE_NAMESPACE}.column_detector.summary": None,
    f"{ENGINE_NAMESPACE}.column_classification": ColumnClassificationPayload,
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

