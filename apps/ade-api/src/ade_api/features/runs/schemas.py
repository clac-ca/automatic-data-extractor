"""Pydantic schemas for ADE run APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ade_api.shared.core.ids import ULIDStr
from ade_api.shared.core.schema import BaseSchema

RunObjectType = Literal["ade.run"]
RunEventObjectType = Literal["ade.run.event"]
RunLogsObjectType = Literal["ade.run.logs"]
RunStatusLiteral = Literal["queued", "running", "succeeded", "failed", "canceled"]
RunEventType = Literal[
    "run.created",
    "run.started",
    "run.log",
    "run.completed",
]

__all__ = [
    "RunCreateOptions",
    "RunCreateRequest",
    "RunCreatedEvent",
    "RunCompletedEvent",
    "RunEvent",
    "RunEventBase",
    "RunLogEntry",
    "RunLogEvent",
    "RunLogsResponse",
    "RunOutputFile",
    "RunOutputListing",
    "RunResource",
    "RunStatusLiteral",
]


class RunCreateOptions(BaseSchema):
    """Optional execution toggles for ADE runs."""

    dry_run: bool = False
    validate_only: bool = False
    input_document_id: ULIDStr | None = None
    input_sheet_name: str | None = Field(
        default=None,
        description="Preferred worksheet to ingest when processing XLSX files.",
        max_length=64,
    )
    input_sheet_names: list[str] | None = Field(
        default=None,
        description="Explicit worksheets to ingest; defaults to all when omitted.",
    )


class RunCreateRequest(BaseSchema):
    """Payload accepted by the run creation endpoint."""

    stream: bool = False
    options: RunCreateOptions = Field(default_factory=RunCreateOptions)


class RunResource(BaseSchema):
    """API representation of a persisted ADE run."""

    id: str
    object: RunObjectType = Field(default="ade.run", alias="object")
    config_id: str
    input_document_id: str | None = Field(
        default=None,
        description="Document ULID staged for this run when provided.",
    )
    input_sheet_name: str | None = Field(
        default=None,
        description="Worksheet name used when ingesting XLSX inputs.",
        max_length=64,
    )
    input_sheet_names: list[str] | None = Field(
        default=None,
        description="Worksheets requested for ingestion when provided.",
    )
    status: RunStatusLiteral

    created: int
    started: int | None = None
    finished: int | None = None

    exit_code: int | None = None
    output_paths: list[str] = Field(default_factory=list)
    processed_files: list[str] = Field(default_factory=list)
    artifact_path: str | None = None
    events_path: str | None = None
    summary: str | None = None
    error_message: str | None = None


class RunEventBase(BaseSchema):
    """Common envelope fields for run stream events."""

    object: RunEventObjectType = Field(default="ade.run.event", alias="object")
    run_id: str
    created: int
    type: RunEventType


class RunCreatedEvent(RunEventBase):
    """Event emitted when a run record is created."""

    type: Literal["run.created"] = "run.created"
    status: RunStatusLiteral
    config_id: str


class RunStartedEvent(RunEventBase):
    """Event emitted once execution begins."""

    type: Literal["run.started"] = "run.started"


class RunLogEvent(RunEventBase):
    """Event encapsulating a streamed log line."""

    type: Literal["run.log"] = "run.log"
    stream: Literal["stdout", "stderr"] = "stdout"
    message: str


class RunCompletedEvent(RunEventBase):
    """Event emitted when execution finishes (success, failure, or cancel)."""

    type: Literal["run.completed"] = "run.completed"
    status: RunStatusLiteral
    exit_code: int | None = None
    error_message: str | None = None
    artifact_path: str | None = None
    events_path: str | None = None
    output_paths: list[str] = Field(default_factory=list)
    processed_files: list[str] = Field(default_factory=list)


RunEvent = RunCreatedEvent | RunStartedEvent | RunLogEvent | RunCompletedEvent


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

    path: str
    byte_size: int


class RunOutputListing(BaseSchema):
    """Collection of files produced by a streaming run."""

    files: list[RunOutputFile] = Field(default_factory=list)
