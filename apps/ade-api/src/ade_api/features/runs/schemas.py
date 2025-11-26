"""Pydantic schemas for ADE run APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from ade_engine.schemas import AdeEvent
from ade_engine.schemas import ArtifactV1 as RunDiagnosticsV1
from pydantic import Field, model_validator

from ade_api.shared.core.ids import ULIDStr
from ade_api.shared.core.schema import BaseSchema
from ade_api.shared.pagination import Page

RunObjectType = Literal["ade.run"]
RunLogsObjectType = Literal["ade.run.logs"]
RunStatusLiteral = Literal["queued", "running", "succeeded", "failed", "canceled"]

__all__ = [
    "RunCreateOptions",
    "RunCreateRequest",
    "RunFilters",
    "RunInput",
    "RunLinks",
    "RunOutput",
    "RunPage",
    "RunLogEntry",
    "RunLogsResponse",
    "RunOutputFile",
    "RunOutputListing",
    "RunResource",
    "RunDiagnosticsV1",
    "RunEventsPage",
    "RunStatusLiteral",
]


class RunCreateOptions(BaseSchema):
    """Optional execution toggles for ADE runs."""

    dry_run: bool = False
    validate_only: bool = False
    force_rebuild: bool = Field(
        default=False,
        description="If true, rebuild the configuration environment before running.",
    )
    document_ids: list[ULIDStr] | None = Field(
        default=None,
        description="Preferred document identifiers to stage as inputs (first is used today).",
    )
    input_document_id: ULIDStr | None = Field(
        default=None,
        description="Deprecated: single document identifier to ingest.",
    )
    input_sheet_name: str | None = Field(
        default=None,
        description="Preferred worksheet to ingest when processing XLSX files.",
        max_length=64,
    )
    input_sheet_names: list[str] | None = Field(
        default=None,
        description="Explicit worksheets to ingest; defaults to all when omitted.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Opaque metadata to propagate with run telemetry.",
    )

    @model_validator(mode="after")
    def _normalize_document_ids(self) -> RunCreateOptions:
        if self.document_ids and not self.input_document_id:
            self.input_document_id = self.document_ids[0]
        elif self.input_document_id and not self.document_ids:
            self.document_ids = [self.input_document_id]
        return self


class RunCreateRequest(BaseSchema):
    """Payload accepted by the run creation endpoint."""

    stream: bool = False
    options: RunCreateOptions = Field(default_factory=RunCreateOptions)


class RunLinks(BaseSchema):
    """Hypermedia links for run-related resources."""

    self: str
    summary: str
    events: str
    logs: str
    logfile: str
    outputs: str
    diagnostics: str


class RunInput(BaseSchema):
    """Input metadata captured for a run."""

    document_ids: list[str] = Field(default_factory=list)
    input_sheet_names: list[str] = Field(default_factory=list)
    input_file_count: int | None = None
    input_sheet_count: int | None = None


class RunOutput(BaseSchema):
    """Output metadata captured for a run."""

    has_outputs: bool = False
    output_count: int = 0
    processed_files: list[str] = Field(default_factory=list)


class RunResource(BaseSchema):
    """API representation of a persisted ADE run."""

    id: str
    object: RunObjectType = Field(default="ade.run", alias="object")
    workspace_id: str
    configuration_id: str
    configuration_version: str | None = None

    status: RunStatusLiteral
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


class RunFilters(BaseSchema):
    """Query parameters for filtering workspace-scoped run listings."""

    status: list[RunStatusLiteral] | None = Field(
        default=None,
        description="Optional run statuses to include (filters out others).",
    )
    input_document_id: ULIDStr | None = Field(
        default=None,
        description="Limit runs to those started for the given document.",
    )


class RunPage(Page[RunResource]):
    """Paginated collection of ``RunResource`` items."""

    items: list[RunResource]


class RunLogEntry(BaseSchema):
    """Single run log entry returned by the logs endpoint."""

    id: int
    created: int
    stream: Literal["stdout", "stderr"]
    message: str


class RunLogsResponse(BaseSchema):
    """Envelope for run log fetch responses."""

    run_id: str
    object: RunLogsObjectType = Field(default="ade.run.logs", alias="object")
    entries: list[RunLogEntry]
    next_after_id: int | None = None


class RunOutputFile(BaseSchema):
    """Single file emitted by a streaming run output directory."""

    name: str
    kind: str | None = None
    content_type: str | None = None
    byte_size: int
    download_url: str | None = None


class RunOutputListing(BaseSchema):
    """Collection of files produced by a streaming run."""

    files: list[RunOutputFile] = Field(default_factory=list)


class RunEventsPage(BaseSchema):
    """Paginated ADE events for a run."""

    items: list[AdeEvent]
    next_cursor: str | None = None
