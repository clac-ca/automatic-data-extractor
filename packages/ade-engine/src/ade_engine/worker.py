"""Job orchestration for the ADE engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .hooks import HookExecutionError, HookLoadError
from .job_service import JobService
from .model import JobResult
from .pipeline.extract import extract_inputs
from .pipeline.output import write_outputs
from .pipeline.state import build_result
from .runtime import resolve_jobs_root
from .sinks import SinkProvider
from .telemetry import TelemetryConfig


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
    """Execute the ADE job pipeline."""

    jobs_root = resolve_jobs_root(jobs_dir)
    service = JobService(config_package=config_package, telemetry=telemetry)
    prepared = service.prepare_job(
        job_id,
        jobs_root=jobs_root,
        manifest_path=manifest_path,
        safe_mode=safe_mode,
        sink_provider=sink_provider,
    )
    job = prepared.job
    artifact = prepared.telemetry.artifact
    events = prepared.telemetry.events
    hooks = prepared.hooks
    structured_logger = prepared.logger
    state_machine = prepared.state_machine
    manifest_ctx = prepared.manifest

    try:
        hooks.call("on_job_start", job=job, artifact=artifact, events=events)

        registry = prepared.registry
        writer_cfg = manifest_ctx.writer
        defaults = manifest_ctx.defaults
        append_unmapped = bool(writer_cfg.get("append_unmapped_columns", True))
        prefix = str(writer_cfg.get("unmapped_prefix", "raw_"))
        sample_size = int(defaults.get("detector_sample_size", 64) or 0)
        threshold = float(defaults.get("mapping_score_threshold", 0.0) or 0.0)

        state: dict[str, Any] = {"tables": [], "job_id": job.job_id}

        def _extract() -> list:
            return extract_inputs(
                job,
                manifest_ctx,
                registry.modules(),
                structured_logger,
                threshold=threshold,
                sample_size=sample_size,
                append_unmapped=append_unmapped,
                unmapped_prefix=prefix,
                state=state,
            )

        def _after_extract(tables: Iterable) -> None:
            hooks.call("on_after_extract", job=job, artifact=artifact, tables=tables)

        def _before_save(tables: Iterable) -> None:
            hooks.call("on_before_save", job=job, artifact=artifact, tables=tables)

        def _write(tables: Iterable) -> Path:
            return write_outputs(job, manifest_ctx, list(tables))

        state_machine.execute(
            extractor=_extract,
            after_extract=_after_extract,
            before_save=_before_save,
            writer=_write,
        )

        result = build_result(state_machine)
        result = service.finalize_success(prepared, result)
        hooks.call("on_job_end", job=job, artifact=artifact, result=result)
        artifact.flush()
        return result
    except Exception as exc:
        return service.finalize_failure(prepared, exc)


__all__ = [
    "HookExecutionError",
    "HookLoadError",
    "run_job",
]
