"""ade_engine runtime package scaffold."""

from __future__ import annotations

from importlib import metadata as _metadata

from pathlib import Path

from ade_engine.core.models import EngineMetadata, JobResult
from ade_engine.core.manifest import ManifestContext
from ade_engine.job_service import JobService
from ade_engine.runtime import (
    ManifestNotFoundError,
    load_config_manifest,
    load_manifest_context,
    resolve_jobs_root,
)
from ade_engine.telemetry.types import TelemetryConfig
from ade_engine.hooks import HookExecutionError, HookLoadError
from ade_engine.sinks import SinkProvider

from . import worker as _worker

try:  # pragma: no cover - executed when package metadata is available
    __version__ = _metadata.version("ade-engine")
except _metadata.PackageNotFoundError:  # pragma: no cover - local source tree fallback
    __version__ = "0.0.0"

DEFAULT_METADATA = EngineMetadata(version=__version__)


def run_job(
    job_id: str,
    *,
    jobs_dir: Path | None = None,
    manifest_path: Path | None = None,
    config_package: str = "ade_config",
    safe_mode: bool = False,
    sink_provider: SinkProvider | None = None,
    telemetry: TelemetryConfig | None = None,
) -> JobResult:
    """Engine interface for running ADE jobs."""

    return _worker.run_job(
        job_id,
        jobs_dir=jobs_dir,
        manifest_path=manifest_path,
        config_package=config_package,
        safe_mode=safe_mode,
        sink_provider=sink_provider,
        telemetry=telemetry,
    )

__all__ = [
    "DEFAULT_METADATA",
    "EngineMetadata",
    "JobService",
    "ManifestContext",
    "ManifestNotFoundError",
    "__version__",
    "load_config_manifest",
    "load_manifest_context",
    "resolve_jobs_root",
    "TelemetryConfig",
    "HookExecutionError",
    "HookLoadError",
    "run_job",
]
