"""Service object that encapsulates ADE job preparation and finalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .hooks import HookRegistry
from .logging import StructuredLogger
from .model import JobContext, JobPaths, JobResult
from .pipeline.registry import ColumnRegistry
from .pipeline.state import PipelineStateMachine, build_result
from .runtime import load_manifest_context
from .schemas.models import ManifestContext
from .sinks import SinkProvider, _now
from .telemetry import TelemetryBindings, TelemetryConfig


@dataclass(slots=True)
class PreparedJob:
    """Runtime assets required to execute an ADE job."""

    job: JobContext
    manifest: ManifestContext
    hooks: HookRegistry
    logger: StructuredLogger
    state_machine: PipelineStateMachine
    telemetry: TelemetryBindings
    registry: ColumnRegistry


class JobService:
    """Coordinate job setup and teardown concerns for the worker."""

    def __init__(
        self,
        *,
        config_package: str = "ade_config",
        telemetry: TelemetryConfig | None = None,
    ) -> None:
        self._config_package = config_package
        self._telemetry_config = telemetry or TelemetryConfig()

    def prepare_job(
        self,
        job_id: str,
        *,
        jobs_root: Path,
        manifest_path: Path | None = None,
        safe_mode: bool = False,
        sink_provider: SinkProvider | None = None,
    ) -> PreparedJob:
        """Resolve runtime dependencies and return a prepared job bundle."""

        paths = _build_job_paths(jobs_root, job_id)
        manifest_ctx = load_manifest_context(
            package=self._config_package, manifest_path=manifest_path
        )
        job = JobContext(
            job_id=job_id,
            manifest=manifest_ctx.raw,
            paths=paths,
            started_at=_now(),
            safe_mode=safe_mode,
        )
        telemetry = self._telemetry_config.bind(
            job,
            paths,
            provider=sink_provider,
        )
        hooks = HookRegistry(manifest_ctx.raw, package=self._config_package)
        logger = StructuredLogger(job, telemetry)
        state_machine = PipelineStateMachine(job, logger)
        telemetry.artifact.start(job=job, manifest=manifest_ctx.raw)
        logger.event("job_started", level="info")

        registry = ColumnRegistry(
            manifest_ctx.column_meta,
            package=self._config_package,
        )

        return PreparedJob(
            job=job,
            manifest=manifest_ctx,
            hooks=hooks,
            logger=logger,
            state_machine=state_machine,
            telemetry=telemetry,
            registry=registry,
        )

    def finalize_success(
        self, prepared: PreparedJob, result: JobResult | None = None
    ) -> JobResult:
        """Mark job success, flush sinks, and build the job result."""

        completed_at = _now()
        prepared.telemetry.artifact.mark_success(
            completed_at=completed_at,
            outputs=prepared.state_machine.output_paths,
        )
        prepared.telemetry.artifact.flush()
        result = result or build_result(prepared.state_machine)
        prepared.logger.event("job_completed", status="succeeded")
        return result

    def finalize_failure(self, prepared: PreparedJob, error: Exception) -> JobResult:
        """Mark job failure, flush sinks, and return an error result."""

        completed_at = _now()
        prepared.telemetry.artifact.mark_failure(
            completed_at=completed_at,
            error=error,
        )
        prepared.logger.note(
            "Job failed",
            level="error",
            error=str(error),
        )
        prepared.telemetry.artifact.flush()
        prepared.logger.event("job_failed", level="error", error=str(error))
        return build_result(prepared.state_machine, error=str(error))


def _build_job_paths(jobs_root: Path, job_id: str) -> JobPaths:
    job_dir = jobs_root / job_id
    input_dir = job_dir / "input"
    output_dir = job_dir / "output"
    logs_dir = job_dir / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    return JobPaths(
        jobs_root=jobs_root,
        job_dir=job_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        logs_dir=logs_dir,
        artifact_path=logs_dir / "artifact.json",
        events_path=logs_dir / "events.ndjson",
    )


__all__ = ["JobService", "PreparedJob"]

