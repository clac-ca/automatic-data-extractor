"""Pydantic models for ade.run_summary/v1."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

RunStatusLiteral = Literal["succeeded", "failed", "cancelled"]


class RunSummaryRun(BaseModel):
    """Identity and lifecycle info for a run summary."""

    id: UUID
    workspace_id: UUID | None = None
    configuration_id: UUID | None = None

    status: RunStatusLiteral
    failure_code: str | None = None
    failure_stage: str | None = None
    failure_message: str | None = None

    engine_version: str | None = None
    config_version: str | None = None

    env_reason: str | None = None
    env_reused: bool | None = None

    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None

    model_config = ConfigDict(extra="forbid")


class RunSummaryCore(BaseModel):
    """Flat, aggregate run metrics."""

    input_file_count: int = 0
    input_sheet_count: int = 0
    table_count: int = 0
    row_count: int | None = None

    canonical_field_count: int = 0
    required_field_count: int = 0
    mapped_field_count: int = 0
    unmapped_column_count: int = 0

    validation_issue_count_total: int = 0
    issue_counts_by_severity: dict[str, int] = Field(default_factory=dict)
    issue_counts_by_code: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class RunSummaryByFile(BaseModel):
    """Breakdown metrics scoped to a single source file."""

    source_file: str
    table_count: int
    row_count: int | None = None

    validation_issue_count_total: int
    issue_counts_by_severity: dict[str, int] = Field(default_factory=dict)
    issue_counts_by_code: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class RunSummaryByField(BaseModel):
    """Breakdown metrics scoped to a canonical field."""

    field: str
    label: str | None = None
    required: bool = False

    mapped: bool = False
    max_score: float | None = None

    validation_issue_count_total: int = 0
    issue_counts_by_severity: dict[str, int] = Field(default_factory=dict)
    issue_counts_by_code: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class RunSummaryBreakdowns(BaseModel):
    """Nested breakdowns for files and fields."""

    by_file: list[RunSummaryByFile] = Field(default_factory=list)
    by_field: list[RunSummaryByField] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RunSummaryV1(BaseModel):
    """Top-level run summary schema (v1)."""

    schema_id: Literal["ade.run_summary/v1"] = Field(
        default="ade.run_summary/v1",
        alias="schema",
        validation_alias=AliasChoices("schema", "schema_id"),
    )
    version: str = "1.0.0"

    run: RunSummaryRun
    core: RunSummaryCore
    breakdowns: RunSummaryBreakdowns

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @property
    def schema(self) -> str:
        return self.schema_id
