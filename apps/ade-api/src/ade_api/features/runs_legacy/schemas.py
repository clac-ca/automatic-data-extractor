"""Pydantic schemas for ADE run APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ade_api.common.ids import UUIDStr
from ade_api.common.pagination import Page
from ade_api.common.schema import BaseSchema
from ade_api.core.models import RunStatus
from ade_api.schemas.event_record import EventRecord

RunObjectType = Literal["ade.run"]

__all__ = [
    "RunCreateOptions",
    "RunCreateRequest",
    "RunFilters",
    "RunInput",
    "RunLinks",
    "RunOutput",
    "RunPage",
    "RunResource",
    "RunEventsPage",
]


class RunCreateOptions(BaseSchema):
    """Optional execution toggles for ADE runs."""

    dry_run: bool = False
    validate_only: bool = False
    force_rebuild: bool = Field(
        default=False,
        description="If true, rebuild the configuration environment before running.",
    )
    input_document_id: UUIDStr | None = Field(
        default=None,
        description="Document identifier to ingest.",
    )
    input_sheet_names: list[str] | None = Field(
        default=None,
        description="Optional worksheet names to ingest when processing XLSX files.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Opaque metadata to propagate with run telemetry.",
    )


class RunCreateRequest(BaseSchema):
    """Payload accepted by the run creation endpoint."""

    options: RunCreateOptions = Field(default_factory=RunCreateOptions)


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


class RunFilters(BaseSchema):
    """Query parameters for filtering workspace-scoped run listings."""

    status: list[RunStatus] | None = Field(
        default=None,
        description="Optional run statuses to include (filters out others).",
    )
    input_document_id: UUIDStr | None = Field(
        default=None,
        description="Limit runs to those started for the given document.",
    )


class RunPage(Page[RunResource]):
    """Paginated collection of ``RunResource`` items."""

    items: list[RunResource]


class RunEventsPage(BaseSchema):
    """Paginated ADE events for a run."""

    items: list[EventRecord]
    next_after_sequence: int | None = None
