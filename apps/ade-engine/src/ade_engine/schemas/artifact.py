"""Artifact JSON schema models."""
from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ade_engine.core.types import RunErrorCode, RunPhase, RunStatus


class ArtifactError(BaseModel):
    """Error details recorded when a run fails."""

    code: RunErrorCode | str
    stage: RunPhase | None = None
    message: str
    details: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class RunArtifact(BaseModel):
    """Run-level information in the artifact."""

    id: str
    status: RunStatus
    started_at: str
    completed_at: str | None = None
    outputs: list[str] = Field(default_factory=list)
    engine_version: str
    error: ArtifactError | None = None

    model_config = ConfigDict(extra="forbid")


class ConfigArtifact(BaseModel):
    """Config metadata captured in the artifact."""

    schema_id: str = Field(alias="schema", validation_alias=AliasChoices("schema", "schema_id"))
    version: str
    name: str | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ScoreContribution(BaseModel):
    detector: str
    delta: float

    model_config = ConfigDict(extra="forbid")


class MappedColumn(BaseModel):
    field: str
    header: str
    source_column_index: int
    score: float
    contributions: list[ScoreContribution] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class UnmappedColumn(BaseModel):
    header: str
    source_column_index: int
    output_header: str

    model_config = ConfigDict(extra="forbid")


class ValidationIssue(BaseModel):
    row_index: int
    field: str
    code: str
    severity: str
    message: str | None = None
    details: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class TableHeader(BaseModel):
    row_index: int
    cells: list[str]

    model_config = ConfigDict(extra="forbid")


class TableArtifact(BaseModel):
    source_file: str
    source_sheet: str | None = None
    table_index: int
    header: TableHeader
    mapped_columns: list[MappedColumn] = Field(default_factory=list)
    unmapped_columns: list[UnmappedColumn] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ArtifactNote(BaseModel):
    timestamp: str
    level: str
    message: str
    details: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class ArtifactV1(BaseModel):
    """Top-level artifact schema (v1)."""

    schema_id: str = Field(
        default="ade.artifact/v1",
        alias="schema",
        validation_alias=AliasChoices("schema", "schema_id"),
    )
    version: str = Field(default="1.0.0")
    run: RunArtifact
    config: ConfigArtifact
    tables: list[TableArtifact] = Field(default_factory=list)
    notes: list[ArtifactNote] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @property
    def schema(self) -> str:
        return self.schema_id
