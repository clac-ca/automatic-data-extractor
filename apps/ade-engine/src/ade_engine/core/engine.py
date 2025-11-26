"""Engine orchestration entrypoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ade_engine.config.loader import ConfigRuntime, load_config_runtime
from ade_engine.config.hook_registry import HookStage
from ade_engine.core.errors import InputError, error_to_run_error
from ade_engine.core.hooks import run_hooks
from ade_engine.core.pipeline.pipeline_runner import execute_pipeline
from ade_engine.core.types import EngineInfo, RunContext, RunError, RunPaths, RunPhase, RunRequest, RunResult, RunStatus
from ade_engine.infra.telemetry import PipelineLogger, TelemetryConfig


def _resolve_paths(request: RunRequest) -> tuple[RunRequest, Path, Path, Path]:
    if bool(request.input_files) == bool(request.input_dir):
        msg = "RunRequest must include exactly one of input_files or input_dir"
        raise InputError(msg)

    input_files = tuple(Path(path).resolve() for path in request.input_files or [])
    input_dir = Path(request.input_dir).resolve() if request.input_dir else input_files[0].parent
    output_dir = Path(request.output_dir).resolve() if request.output_dir else input_dir / "output"
    logs_dir = Path(request.logs_dir).resolve() if request.logs_dir else input_dir / "logs"

    normalized = RunRequest(
        config_package=request.config_package,
        manifest_path=Path(request.manifest_path).resolve() if request.manifest_path else None,
        input_files=input_files if input_files else None,
        input_dir=input_dir,
        input_sheets=request.input_sheets,
        output_dir=output_dir,
        logs_dir=logs_dir,
        metadata=dict(request.metadata) if request.metadata else {},
    )
    return normalized, input_dir, output_dir, logs_dir


def _ensure_dirs(output_dir: Path, logs_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)


class Engine:
    """Primary runtime entrypoint."""

    def __init__(self, *, telemetry: TelemetryConfig | None = None, engine_info: EngineInfo | None = None) -> None:
        self.telemetry = telemetry or TelemetryConfig()
        self.engine_info = engine_info or EngineInfo(name="ade-engine", version="0.2.0")
        self.logger = logging.getLogger(__name__)

    def run(self, request: RunRequest | None = None, **kwargs: Any) -> RunResult:
        req = request or RunRequest(**kwargs)
        phase: RunPhase | None = RunPhase.INITIALIZATION

        try:
            normalized_request, input_dir, output_dir, logs_dir = _resolve_paths(req)
            _ensure_dirs(output_dir, logs_dir)

            run_ctx = RunContext(
                run_id=str(uuid4()),
                metadata=dict(normalized_request.metadata) if normalized_request.metadata else {},
                manifest=None,
                paths=RunPaths(
                    input_dir=input_dir,
                    output_dir=output_dir,
                    logs_dir=logs_dir,
                ),
                started_at=datetime.now(timezone.utc),
            )

            phase = RunPhase.LOAD_CONFIG
            runtime: ConfigRuntime = load_config_runtime(
                package=normalized_request.config_package, manifest_path=normalized_request.manifest_path
            )
            run_ctx.manifest = runtime.manifest

            event_sink = self.telemetry.build_sink(run_ctx) if self.telemetry else None
            pipeline_logger = PipelineLogger(run=run_ctx, event_sink=event_sink)

            pipeline_logger.event(
                "started",
                level=None,
                engine_version=self.engine_info.version,
            )

            phase = RunPhase.HOOKS
            run_hooks(
                HookStage.ON_RUN_START,
                runtime.hooks,
                run=run_ctx,
                manifest=runtime.manifest,
                tables=None,
                workbook=None,
                result=None,
                logger=pipeline_logger,
            )

            phase = RunPhase.EXTRACTING
            normalized_tables, output_paths, processed_files = execute_pipeline(
                request=normalized_request,
                run=run_ctx,
                runtime=runtime,
                pipeline_logger=pipeline_logger,
                logger=self.logger,
            )

            phase = RunPhase.COMPLETED
            pipeline_logger.event(
                "completed",
                level=None,
                status="succeeded",
                output_paths=[str(path) for path in output_paths],
                processed_files=processed_files,
            )

            run_ctx.completed_at = datetime.now(timezone.utc)
            provisional = RunResult(
                status=RunStatus.SUCCEEDED,
                error=None,
                run_id=run_ctx.run_id,
                output_paths=output_paths,
                logs_dir=logs_dir,
                processed_files=processed_files,
            )

            phase = RunPhase.HOOKS
            run_hooks(
                HookStage.ON_RUN_END,
                runtime.hooks,
                run=run_ctx,
                manifest=runtime.manifest,
                tables=normalized_tables,
                workbook=None,
                result=provisional,
                logger=pipeline_logger,
            )

            return provisional

        except Exception as exc:  # pragma: no cover - exercised via tests
            error: RunError = error_to_run_error(exc, stage=phase)
            self.logger.exception("Run failed", exc_info=exc)

            try:
                if 'event_sink' in locals() and event_sink:
                    pipeline_logger._emit(  # pylint: disable=protected-access
                        "completed",
                        run_payload={
                            "status": "failed",
                            "error": {
                                "code": error.code,
                                "stage": error.stage.value if error.stage else None,
                                "message": error.message,
                            },
                        },
                    )
            except Exception:
                pass

            if "run_ctx" in locals():
                run_ctx.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]

            return RunResult(
                status=RunStatus.FAILED,
                error=error,
                run_id=locals().get("run_ctx", RunContext(run_id="", metadata={}, manifest=None, paths=None, started_at=datetime.now(timezone.utc))).run_id,  # type: ignore[arg-type]
                output_paths=(),
                logs_dir=logs_dir if 'logs_dir' in locals() else Path("logs"),
                processed_files=(),
            )


__all__ = ["Engine"]
