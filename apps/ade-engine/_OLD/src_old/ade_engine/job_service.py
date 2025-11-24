"""Service object that encapsulates ADE job preparation and finalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ade_engine.config.loader import load_manifest, resolve_input_sheets
from ade_engine.core.phases import PipelinePhase
from ade_engine.schemas import ManifestContext

from ade_engine.hooks import HookContext, HookRegistry, HookStage
from ade_engine.core.models import JobContext, JobPaths, JobResult
from ade_engine.telemetry.logging import PipelineLogger
from ade_engine.telemetry.sinks import SinkProvider, _now
from ade_engine.telemetry.types import TelemetryBindings, TelemetryConfig
from .pipeline.registry import ColumnRegistry
from .pipeline.runner import PipelineRunner
from .pipeline.stages import ExtractStage, WriteStage


@dataclass(slots=True)
class PreparedJob:
    """Runtime assets required to execute an ADE job."""

    job: JobContext
    manifest: ManifestContext
    hooks: HookRegistry
    logger: PipelineLogger
    pipeline: PipelineRunner
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
        manifest_ctx = load_manifest(
            package=self._config_package, manifest_path=manifest_path
        )
        metadata: dict[str, Any] = {}
        if self._telemetry_config.correlation_id:
            metadata["run_id"] = self._telemetry_config.correlation_id
        sheet_list = resolve_input_sheets()
        if sheet_list:
            metadata["input_sheet_names"] = sheet_list
            if len(sheet_list) == 1:
                metadata["input_sheet_name"] = sheet_list[0]
        job = JobContext(
            job_id=job_id,
            manifest=manifest_ctx.raw,
            manifest_model=manifest_ctx.model,
            paths=paths,
            started_at=_now(),
            safe_mode=safe_mode,
            metadata=metadata,
        )
        telemetry = self._telemetry_config.bind(
            job,
            paths,
            provider=sink_provider,
        )
        hooks = HookRegistry(manifest_ctx, package=self._config_package)
        logger = PipelineLogger(job, telemetry)
        pipeline = PipelineRunner(job, logger)
        telemetry.artifact.start(job=job, manifest=manifest_ctx.raw)
        logger.event("job_started", level="info")

        registry = ColumnRegistry(
            manifest_ctx.column_models,
            package=self._config_package,
        )

        return PreparedJob(
            job=job,
            manifest=manifest_ctx,
            hooks=hooks,
            logger=logger,
            pipeline=pipeline,
            telemetry=telemetry,
            registry=registry,
        )

    def run(self, prepared: PreparedJob) -> JobResult:
        """Execute a prepared job and return its result."""

        job = prepared.job
        artifact = prepared.telemetry.artifact
        events = prepared.telemetry.events
        hooks = prepared.hooks
        logger = prepared.logger
        pipeline = prepared.pipeline
        manifest_ctx = prepared.manifest

        try:
            hooks.call(
                HookStage.ON_JOB_START,
                HookContext(job=job, artifact=artifact, events=events),
            )

            registry = prepared.registry
            writer_cfg = manifest_ctx.writer
            defaults = manifest_ctx.defaults
            append_unmapped = bool(writer_cfg.append_unmapped_columns)
            prefix = str(writer_cfg.unmapped_prefix)
            sample_size = int(defaults.detector_sample_size or 64)
            threshold = float(defaults.mapping_score_threshold or 0.0)

            extract_stage = ExtractStage(
                manifest=manifest_ctx,
                modules=registry.modules(),
                threshold=threshold,
                sample_size=sample_size,
                append_unmapped=append_unmapped,
                unmapped_prefix=prefix,
            )
            write_stage = WriteStage(manifest=manifest_ctx)

            def _run_extract(job_ctx: Any, _: Any, log: PipelineLogger) -> list:
                tables = extract_stage.run(job_ctx, None, log)
                hooks.call(
                    HookStage.ON_AFTER_EXTRACT,
                    HookContext(job=job_ctx, artifact=artifact, events=events, tables=tables),
                )
                return tables

            def _run_write(job_ctx: Any, tables: Any, log: PipelineLogger) -> Path:
                hooks.call(
                    HookStage.ON_BEFORE_SAVE,
                    HookContext(job=job_ctx, artifact=artifact, events=events, tables=list(tables)),
                )
                return write_stage.run(job_ctx, list(tables), log)

            pipeline.run(extract_stage=_run_extract, write_stage=_run_write)
            result = self.finalize_success(prepared, None)
            hooks.call(
                HookStage.ON_JOB_END,
                HookContext(
                    job=job,
                    artifact=artifact,
                    events=events,
                    tables=pipeline.tables,
                    result=result,
                ),
            )
            artifact.flush()
            return result
        except Exception as exc:  # pragma: no cover - exercised via integration
            if pipeline.phase is not PipelinePhase.FAILED:
                pipeline.phase = PipelinePhase.FAILED
            result = self.finalize_failure(prepared, exc)
            try:
                hooks.call(
                    HookStage.ON_JOB_END,
                    HookContext(
                        job=job,
                        artifact=artifact,
                        events=events,
                        tables=pipeline.tables,
                        result=result,
                    ),
                )
            finally:
                artifact.flush()
            return result

    def finalize_success(
        self, prepared: PreparedJob, result: JobResult | None = None
    ) -> JobResult:
        """Mark job success, flush sinks, and build the job result."""

        completed_at = _now()
        prepared.telemetry.artifact.mark_success(
            completed_at=completed_at,
            outputs=prepared.pipeline.output_paths,
        )
        prepared.telemetry.artifact.flush()
        result = result or _build_result_from_pipeline(prepared.pipeline)
        prepared.logger.event("job_completed", status="succeeded")
        return result

    def finalize_failure(self, prepared: PreparedJob, error: Exception) -> JobResult:
        """Mark job failure, flush sinks, and return an error result."""

        completed_at = _now()
        if prepared.pipeline.phase is not PipelinePhase.FAILED:
            prepared.pipeline.phase = PipelinePhase.FAILED
            prepared.logger.transition(PipelinePhase.FAILED.value, error=str(error))
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
        return _build_result_from_pipeline(prepared.pipeline, error=str(error))


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


def _build_result_from_pipeline(pipeline: PipelineRunner, error: str | None = None) -> JobResult:
    status = "failed" if error or pipeline.phase is PipelinePhase.FAILED else "succeeded"
    processed = tuple(getattr(table, "source_name", "") for table in pipeline.tables)
    return JobResult(
        job_id=pipeline.job.job_id,
        status=status,
        artifact_path=pipeline.job.paths.artifact_path,
        events_path=pipeline.job.paths.events_path,
        output_paths=pipeline.output_paths,
        processed_files=processed,
        error=error,
    )


__all__ = ["JobService", "PreparedJob"]
