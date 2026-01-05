"""Pydantic schemas for ADE run APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ade_api.common.events import EventRecord
from ade_api.common.ids import UUIDStr
from ade_api.common.listing import ListPage
from ade_api.common.schema import BaseSchema
from ade_api.models import RunStatus

RunObjectType = Literal["ade.run"]
RunLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

__all__ = [
    "RunBatchCreateOptions",
    "RunBatchCreateRequest",
    "RunWorkspaceBatchCreateRequest",
    "RunBatchCreateResponse",
    "RunCreateOptionsBase",
    "RunCreateOptions",
    "RunCreateRequest",
    "RunWorkspaceCreateRequest",
    "RunInput",
    "RunMetricsResource",
    "RunFieldResource",
    "RunColumnResource",
    "RunLinks",
    "RunOutput",
    "RunOutputSheet",
    "RunPage",
    "RunResource",
    "RunEventsPage",
]


class RunCreateOptionsBase(BaseSchema):
    """Optional execution toggles for ADE runs."""

    dry_run: bool = False
    validate_only: bool = False
    force_rebuild: bool = Field(
        default=False,
        description="If true, rebuild the configuration environment before running.",
    )
    log_level: RunLogLevel | None = Field(
        default=None,
        description="Engine log level passed as --log-level to ade_engine.",
    )
    input_sheet_names: list[str] | None = Field(
        default=None,
        description="Optional worksheet names to ingest when processing XLSX files.",
    )
    active_sheet_only: bool = Field(
        default=False,
        description="If true, process only the active worksheet when ingesting XLSX files.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Opaque metadata to propagate with run telemetry.",
    )

    @model_validator(mode="after")
    def _validate_sheet_options(self) -> RunCreateOptionsBase:
        if self.active_sheet_only and self.input_sheet_names:
            raise ValueError("active_sheet_only cannot be combined with input_sheet_names")
        return self


class RunCreateOptions(RunCreateOptionsBase):
    """Execution toggles for a single ADE run."""

    input_document_id: UUIDStr = Field(
        ...,
        description="Document identifier to ingest.",
    )


class RunCreateRequest(BaseSchema):
    """Payload accepted by the run creation endpoint."""

    options: RunCreateOptions = Field(default_factory=RunCreateOptions)


class RunWorkspaceCreateRequest(BaseSchema):
    """Payload accepted by the workspace run creation endpoint."""

    input_document_id: UUIDStr = Field(
        ...,
        description="Document identifier to ingest.",
    )
    configuration_id: UUIDStr | None = Field(
        default=None,
        description="Optional configuration identifier (defaults to the active configuration).",
    )
    options: RunCreateOptionsBase = Field(default_factory=RunCreateOptionsBase)


class RunBatchCreateOptions(BaseSchema):
    """Execution toggles for batch ADE runs (per-document input)."""

    dry_run: bool = False
    validate_only: bool = False
    force_rebuild: bool = Field(
        default=False,
        description="If true, rebuild the configuration environment before running.",
    )
    log_level: RunLogLevel | None = Field(
        default=None,
        description="Engine log level passed as --log-level to ade_engine.",
    )
    active_sheet_only: bool = Field(
        default=False,
        description="If true, process only the active worksheet when ingesting XLSX files.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Opaque metadata to propagate with run telemetry.",
    )


class RunBatchCreateRequest(BaseSchema):
    """Payload accepted by the batch run creation endpoint."""

    document_ids: list[UUIDStr] = Field(
        ...,
        min_length=1,
        description="Documents to enqueue as individual runs (all-or-nothing).",
    )
    options: RunBatchCreateOptions = Field(default_factory=RunBatchCreateOptions)


class RunWorkspaceBatchCreateRequest(BaseSchema):
    """Payload accepted by the workspace batch run creation endpoint."""

    document_ids: list[UUIDStr] = Field(
        ...,
        min_length=1,
        description="Documents to enqueue as individual runs (all-or-nothing).",
    )
    configuration_id: UUIDStr | None = Field(
        default=None,
        description="Optional configuration identifier (defaults to the active configuration).",
    )
    options: RunBatchCreateOptions = Field(default_factory=RunBatchCreateOptions)


class RunBatchCreateResponse(BaseSchema):
    """Response envelope for batch run creation."""

    runs: list[RunResource]


class RunLinks(BaseSchema):
    """Hypermedia links for run-related resources."""

    self: str
    events: str
    events_stream: str
    events_download: str
    logs: str
    input: str
    input_download: str
    output: str
    output_download: str
    output_metadata: str


class RunInput(BaseSchema):
    """Input metadata captured for a run."""

    document_id: UUIDStr | None = None
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    download_url: str | None = None
    input_sheet_names: list[str] | None = None
    input_file_count: int | None = None
    input_sheet_count: int | None = None


class RunOutput(BaseSchema):
    """Output metadata captured for a run."""

    ready: bool = False
    download_url: str | None = None
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    has_output: bool = False
    output_path: str | None = None
    processed_file: str | None = None


class RunOutputSheet(BaseSchema):
    """Descriptor for a worksheet or single-sheet run output."""

    name: str
    index: int = Field(ge=0)
    kind: Literal["worksheet", "file"] = "worksheet"
    is_active: bool = False


class RunMetricsResource(BaseSchema):
    """Aggregate run metrics derived from engine.run.completed."""

    evaluation_outcome: str | None = None
    evaluation_findings_total: int | None = None
    evaluation_findings_info: int | None = None
    evaluation_findings_warning: int | None = None
    evaluation_findings_error: int | None = None

    validation_issues_total: int | None = None
    validation_issues_info: int | None = None
    validation_issues_warning: int | None = None
    validation_issues_error: int | None = None
    validation_max_severity: str | None = None

    workbook_count: int | None = None
    sheet_count: int | None = None
    table_count: int | None = None

    row_count_total: int | None = None
    row_count_empty: int | None = None

    column_count_total: int | None = None
    column_count_empty: int | None = None
    column_count_mapped: int | None = None
    column_count_unmapped: int | None = None

    field_count_expected: int | None = None
    field_count_detected: int | None = None
    field_count_not_detected: int | None = None

    cell_count_total: int | None = None
    cell_count_non_empty: int | None = None


class RunFieldResource(BaseSchema):
    """Field-level detection summary for a run."""

    field: str
    label: str | None = None
    detected: bool
    best_mapping_score: float | None = None
    occurrences_tables: int
    occurrences_columns: int


class RunColumnResource(BaseSchema):
    """Detected column details for a run table."""

    workbook_index: int
    workbook_name: str
    sheet_index: int
    sheet_name: str
    table_index: int
    column_index: int
    header_raw: str | None = None
    header_normalized: str | None = None
    non_empty_cells: int
    mapping_status: Literal["mapped", "unmapped"]
    mapped_field: str | None = None
    mapping_score: float | None = None
    mapping_method: str | None = None
    unmapped_reason: str | None = None


class RunResource(BaseSchema):
    """API representation of a persisted ADE run."""

    id: UUIDStr
    object: RunObjectType = Field(default="ade.run", alias="object")
    workspace_id: UUIDStr
    configuration_id: UUIDStr
    build_id: UUIDStr | None = None

    status: RunStatus
    failure_code: str | None = None
    failure_stage: str | None = None
    failure_message: str | None = None

    engine_version: str | None = None
    config_version: str | None = None
    env_reason: str | None = None
    env_reused: bool | None = None

    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None

    input: RunInput = Field(default_factory=RunInput)
    output: RunOutput = Field(default_factory=RunOutput)
    links: RunLinks
    events_url: str | None = None
    events_stream_url: str | None = None
    events_download_url: str | None = None


class RunPage(ListPage[RunResource]):
    """Paginated collection of ``RunResource`` items."""

    items: list[RunResource]


class RunEventsPage(BaseSchema):
    """Paginated ADE events for a run."""

    items: list[EventRecord]
    next_after_sequence: int | None = None
