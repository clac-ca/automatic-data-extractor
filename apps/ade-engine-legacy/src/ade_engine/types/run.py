"""Run-level types for the engine."""

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
    """Configuration for a single engine run."""

    config_package: str = "ade_config"
    manifest_path: Path | None = None
    input_file: Path | None = None
    input_sheets: list[str] | None = None
    output_dir: Path | None = None
    output_file: Path | None = None
    logs_dir: Path | None = None
    logs_file: Path | None = None


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
    logs_dir: Path
    processed_file: str | None
    started_at: datetime | None = None
    completed_at: datetime | None = None


__all__ = ["RunError", "RunErrorCode", "RunRequest", "RunResult", "RunStatus"]
