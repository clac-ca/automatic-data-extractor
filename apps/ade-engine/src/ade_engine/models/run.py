"""Run-level types for the engine.

These types are intentionally small and explicit:
- ``RunRequest`` is user-provided input/options (may include relative paths).
- The engine normalizes paths internally before executing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


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


@dataclass
class RunRequest:
    """Inputs and options for a single engine run."""

    config_package: Path
    input_file: Path
    input_sheets: list[str] | None = None
    active_sheet_only: bool = False

    # Output planning:
    # - If output_path is provided, it wins.
    # - Else, if output_dir is provided, write <output_dir>/<input_stem>_normalized.xlsx
    # - Else, write alongside the input file.
    output_dir: Path | None = None
    output_path: Path | None = None

    # Logging:
    # - logs_dir/logs_path are optional; if omitted, the engine logs only to stderr/stdout.
    # - if logs_dir is provided, logs_path defaults to <logs_dir>/<input_stem>_engine.log|engine_events.ndjson
    #   (based on log_format).
    logs_dir: Path | None = None
    logs_path: Path | None = None


@dataclass(frozen=True)
class RunError:
    """Structured error info returned to callers and recorded in artifacts."""

    code: RunErrorCode
    stage: str | None
    message: str


@dataclass(frozen=True)
class RunResult:
    """Outcome summary for a run."""

    status: RunStatus
    error: RunError | None
    output_path: Path | None
    logs_dir: Path | None
    processed_file: str | None
    started_at: datetime | None = None
    completed_at: datetime | None = None


__all__ = ["RunError", "RunErrorCode", "RunRequest", "RunResult", "RunStatus"]
