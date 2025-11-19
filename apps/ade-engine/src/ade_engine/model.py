"""Data structures shared across :mod:`ade_engine` modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ade_engine.schemas import ManifestV1


@dataclass(frozen=True, slots=True)
class EngineMetadata:
    """Describes the installed ade_engine distribution."""

    name: str = "ade-engine"
    version: str = "0.0.0"
    description: str | None = None


@dataclass(frozen=True, slots=True)
class JobPaths:
    """Resolved paths for a job's working directory structure."""

    jobs_root: Path
    job_dir: Path
    input_dir: Path
    output_dir: Path
    logs_dir: Path
    artifact_path: Path
    events_path: Path


@dataclass(slots=True)
class JobContext:
    """Mutable context shared across the runtime."""

    job_id: str
    manifest: dict[str, Any]
    manifest_model: ManifestV1 | None = None
    paths: JobPaths
    started_at: datetime
    safe_mode: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JobResult:
    """Outcome returned by :func:`ade_engine.worker.run_job`."""

    job_id: str
    status: str
    artifact_path: Path
    events_path: Path
    output_paths: tuple[Path, ...]
    processed_files: tuple[str, ...] = ()
    error: str | None = None


__all__ = ["EngineMetadata", "JobContext", "JobPaths", "JobResult"]
