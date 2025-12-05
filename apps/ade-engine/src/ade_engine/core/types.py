"""Core runtime types for ade_engine.

These data structures mirror the terminology defined in the engine docs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID


class RunStatus(str, Enum):
    """Overall run outcome."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunErrorCode(str, Enum):
    """Categorization for failures surfaced to callers."""

    CONFIG_ERROR = "config_error"
    INPUT_ERROR = "input_error"
    HOOK_ERROR = "hook_error"
    PIPELINE_ERROR = "pipeline_error"
    UNKNOWN_ERROR = "unknown_error"


class RunPhase(str, Enum):
    """Pipeline phases used for telemetry and error mapping."""

    INITIALIZATION = "initialization"
    LOAD_CONFIG = "load_config"
    EXTRACTING = "extracting"
    MAPPING = "mapping"
    NORMALIZING = "normalizing"
    WRITING_OUTPUT = "writing_output"
    HOOKS = "hooks"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class EngineInfo:
    """Minimal engine metadata for telemetry and CLI."""

    name: str = "ade-engine"
    version: str = "0.0.0"
    description: str | None = None


@dataclass
class RunRequest:
    """Configuration for a single engine run."""

    config_package: str = "ade_config"
    manifest_path: Path | None = None

    input_file: Path | None = None

    input_sheets: Sequence[str] | None = None

    output_dir: Path | None = None
    output_file: Path | None = None
    events_dir: Path | None = None
    events_file: Path | None = None

    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class RunPaths:
    """Resolved filesystem layout for a run."""

    input_file: Path
    output_dir: Path
    output_file: Path
    events_dir: Path | None
    events_file: Path | None


@dataclass
class RunContext:
    """Per-run state shared across the pipeline and hooks."""

    run_id: UUID
    metadata: dict[str, Any]
    manifest: Any
    paths: RunPaths
    started_at: datetime
    completed_at: datetime | None = None
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunError:
    """Structured error info returned to callers and recorded in artifacts."""

    code: RunErrorCode
    stage: RunPhase | None
    message: str


@dataclass(frozen=True)
class RunResult:
    """Outcome summary for a run."""

    status: RunStatus
    error: RunError | None
    run_id: UUID
    output_path: Path | None
    logs_dir: Path
    processed_file: str | None


@dataclass
class ExtractedTable:
    """Table detected in a source file before mapping or normalization."""

    source_file: Path
    source_sheet: str | None
    table_index: int
    header_row: list[str]
    data_rows: list[list[Any]]
    header_row_index: int
    first_data_row_index: int
    last_data_row_index: int


@dataclass(frozen=True)
class ScoreContribution:
    """Individual detector contribution to a column mapping score."""

    field: str
    detector: str
    delta: float


@dataclass(frozen=True)
class MappedColumn:
    """Mapping of a physical column to a canonical field."""

    field: str
    header: str
    source_column_index: int
    score: float
    contributions: tuple[ScoreContribution, ...]
    is_required: bool = False
    is_satisfied: bool = True


@dataclass(frozen=True)
class UnmappedColumn:
    """Physical column preserved without a canonical field mapping."""

    header: str
    source_column_index: int
    output_header: str


@dataclass
class ColumnMap:
    """Column mapping results for a table."""

    mapped_columns: list[MappedColumn]
    unmapped_columns: list[UnmappedColumn]


@dataclass
class MappedTable:
    """Wrapper pairing an extracted table with its column map."""

    extracted: ExtractedTable
    column_map: ColumnMap


@dataclass(frozen=True)
class ValidationIssue:
    """Validation problem associated with a canonical field and row."""

    row_index: int
    field: str
    code: str
    severity: str
    message: str | None
    details: dict[str, Any] | None = None


@dataclass
class NormalizedTable:
    """Normalized output table with validation info."""

    mapped: MappedTable
    rows: list[list[Any]]
    validation_issues: list[ValidationIssue]
    output_sheet_name: str
