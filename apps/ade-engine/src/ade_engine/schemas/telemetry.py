"""Canonical ADE event envelope and payload helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdeEventPayload(BaseModel):
    """Base class for structured AdeEvent payloads."""

    model_config = ConfigDict(extra="allow")


class ConsoleLinePayload(AdeEventPayload):
    scope: str
    stream: str
    level: str = "info"
    message: str
    phase: str | None = None
    logger: str | None = None
    engine_timestamp: int | float | str | None = None


class BuildCreatedPayload(AdeEventPayload):
    status: str = "queued"
    reason: str
    engine_spec: str | None = None
    engine_version_hint: str | None = None
    python_bin: str | None = None
    should_build: bool = True


class BuildStartedPayload(AdeEventPayload):
    status: str = "building"
    reason: str | None = None


class BuildPhaseStartedPayload(AdeEventPayload):
    phase: str
    message: str | None = None


class BuildPhaseCompletedPayload(AdeEventPayload):
    phase: str
    status: str
    duration_ms: int | None = None
    message: str | None = None


class BuildCompletedPayload(AdeEventPayload):
    status: str
    exit_code: int | None = None
    summary: str | None = None
    duration_ms: int | None = None
    env: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class RunQueuedPayload(AdeEventPayload):
    status: str = "queued"
    mode: str
    options: dict[str, Any] = Field(default_factory=dict)
    queued_by: dict[str, Any] | None = None


class RunStartedPayload(AdeEventPayload):
    status: str = "in_progress"
    mode: str
    engine_version: str | None = None
    config_version: str | None = None
    env: dict[str, Any] | None = None


class RunPhaseStartedPayload(AdeEventPayload):
    phase: str
    message: str | None = None


class RunPhaseCompletedPayload(AdeEventPayload):
    phase: str
    status: str
    duration_ms: int | None = None
    message: str | None = None
    metrics: dict[str, Any] | None = None


class ColumnDetectorContributionPayload(AdeEventPayload):
    detector: str
    delta: float


class ColumnDetectorCandidatePayload(AdeEventPayload):
    column_index: int | None = None
    source_column_index: int | None = None
    header: str | None = None
    score: float | None = None
    passed_threshold: bool | None = None
    contributions: list[ColumnDetectorContributionPayload] | None = None


class RunColumnDetectorScorePayload(AdeEventPayload):
    source_file: str
    source_sheet: str | None = None
    table_index: int
    field: str
    threshold: float | None = None
    chosen: ColumnDetectorCandidatePayload | None = None
    candidates: list[ColumnDetectorCandidatePayload] | None = None


class RowDetectorContributionPayload(AdeEventPayload):
    detector: str
    scores: dict[str, float] | None = None


class RowDetectorTriggerPayload(AdeEventPayload):
    row_index: int
    header_score: float | None = None
    data_score: float | None = None
    contributions: list[RowDetectorContributionPayload] | None = None
    sample: list[Any] | None = None


class RunRowDetectorScorePayload(AdeEventPayload):
    source_file: str
    source_sheet: str | None = None
    table_index: int
    thresholds: dict[str, float] | None = None
    header_row_index: int | None = None
    data_row_start_index: int | None = None
    data_row_end_index: int | None = None
    trigger: RowDetectorTriggerPayload | None = None


class RunTableSummaryPayload(AdeEventPayload):
    table_id: str
    source_file: str
    source_sheet: str | None = None
    file_index: int | None = None
    sheet_index: int | None = None
    table_index: int | None = None
    row_count: int | None = None
    column_count: int | None = None
    mapping: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class RunValidationSummaryPayload(AdeEventPayload):
    issues_total: int
    issues_by_severity: dict[str, int]
    issues_by_code: dict[str, int]
    issues_by_field: dict[str, int]
    max_severity: str | None


class RunValidationIssuePayload(AdeEventPayload):
    severity: str | None = None
    code: str | None = None
    field: str | None = None
    row: int | None = None
    message: str | None = None


class RunErrorPayload(AdeEventPayload):
    stage: str
    code: str
    message: str
    phase: str | None = None
    details: dict[str, Any] | None = None


class RunCompletedPayload(AdeEventPayload):
    status: str
    failure: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


class AdeEvent(BaseModel):
    """Canonical ADE event envelope for build + run streaming."""

    type: str
    event_id: str | None = None
    created_at: datetime
    sequence: int | None = None
    source: str | None = None

    workspace_id: UUID | None = None
    configuration_id: UUID | None = None
    run_id: UUID | None = None
    build_id: UUID | None = None

    payload: AdeEventPayload | dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)

    def payload_dict(self) -> dict[str, Any]:
        if self.payload is None:
            return {}
        if isinstance(self.payload, BaseModel):
            return self.payload.model_dump()
        if isinstance(self.payload, dict):
            return self.payload
        return {}


TelemetryEnvelope = AdeEvent


class TelemetryEvent(BaseModel):  # pragma: no cover - legacy placeholder
    event: str
    level: str
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


__all__ = [
    "AdeEvent",
    "AdeEventPayload",
    "BuildCompletedPayload",
    "BuildCreatedPayload",
    "BuildPhaseCompletedPayload",
    "BuildPhaseStartedPayload",
    "BuildStartedPayload",
    "ColumnDetectorCandidatePayload",
    "ColumnDetectorContributionPayload",
    "ConsoleLinePayload",
    "RunCompletedPayload",
    "RunErrorPayload",
    "RunPhaseCompletedPayload",
    "RunPhaseStartedPayload",
    "RunColumnDetectorScorePayload",
    "RunRowDetectorScorePayload",
    "RunQueuedPayload",
    "RunStartedPayload",
    "RunTableSummaryPayload",
    "RunValidationIssuePayload",
    "RunValidationSummaryPayload",
    "RowDetectorContributionPayload",
    "RowDetectorTriggerPayload",
    "TelemetryEnvelope",
    "TelemetryEvent",
]
