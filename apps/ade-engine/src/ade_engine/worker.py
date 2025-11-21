"""Job orchestration for the ADE engine (legacy adapter)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ade_engine.config.loader import resolve_jobs_root
from ade_engine.core.manifest import EngineDefaults, EngineWriter
from ade_engine.core.models import JobResult
from ade_engine.core.phases import PipelinePhase
from ade_engine.hooks import (
    HookContext,
    HookExecutionError,
    HookLoadError,
    HookRegistry,
    HookStage,
)
from .job_service import JobService
from .pipeline.runner import PipelineRunner
from .pipeline.stages import ExtractStage, WriteStage
from .telemetry.sinks import SinkProvider
from .telemetry.types import TelemetryConfig


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
    """Execute the ADE job pipeline (legacy adapter)."""

    jobs_root = resolve_jobs_root(jobs_dir)
    service = JobService(config_package=config_package, telemetry=telemetry)
    prepared = service.prepare_job(
        job_id,
        jobs_root=jobs_root,
        manifest_path=manifest_path,
        safe_mode=safe_mode,
        sink_provider=sink_provider,
    )
    return service.run(prepared)


__all__ = [
    "HookExecutionError",
    "HookLoadError",
    "run_job",
]
