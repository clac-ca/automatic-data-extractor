"""Engine orchestration entrypoints."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from uuid import uuid7
except ImportError:  # pragma: no cover - fallback for environments without uuid7
    from uuid import uuid4 as uuid7

from ade_engine.config.loader import ConfigRuntime, load_config_runtime
from ade_engine.config.hook_registry import HookStage
from ade_engine.core.errors import ConfigError, InputError, error_to_run_error
from ade_engine.core.hooks import run_hooks
from ade_engine.core.pipeline.pipeline_runner import execute_pipeline
from ade_engine.core.pipeline.summary_builder import SummaryAggregator
from ade_engine.core.types import EngineInfo, RunContext, RunError, RunPaths, RunPhase, RunRequest, RunResult, RunStatus
from ade_engine.infra.event_emitter import ConfigEventEmitter, EngineEventEmitter
from ade_engine.infra.logging import build_run_logger
from ade_engine.infra.telemetry import FileEventSink, TelemetryConfig, _coerce_uuid


def _normalize_config_source(config_package: str | None) -> tuple[str, Path | None]:
    """
    Accept either a module name or a filesystem path to a config package.

    Returns:
        (import_name, sys_path_entry) where sys_path_entry should be inserted
        ahead of imports when provided.
    """

    package_value = config_package or "ade_config"
    candidate_path = Path(package_value)
    if not candidate_path.exists():
        return package_value, None

    if candidate_path.is_file():
        msg = f"Config package path must be a directory, got file '{candidate_path}'"
        raise ConfigError(msg)

    package_dirs = [
        candidate_path if candidate_path.name == "ade_config" else None,
        candidate_path / "ade_config",
        candidate_path / "src" / "ade_config",
    ]

    for pkg_dir in package_dirs:
        if pkg_dir is None:
            continue
        manifest = pkg_dir / "manifest.json"
        if manifest.exists():
            return pkg_dir.name, pkg_dir.parent

    raise ConfigError(
        "Unable to locate manifest.json under config path "
        f"'{candidate_path}'. Expected it in 'ade_config/manifest.json' or 'src/ade_config/manifest.json'."
    )


def _resolve_paths(request: RunRequest) -> tuple[RunRequest, Path, Path | None, Path | None, Path | None]:
    config_package, config_sys_path = _normalize_config_source(request.config_package)

    if request.input_file is None:
        msg = "RunRequest must include input_file"
        raise InputError(msg)

    input_file = Path(request.input_file).resolve()
    output_dir = Path(request.output_dir).resolve() if request.output_dir else input_file.parent / "output"
    output_file = Path(request.output_file).resolve() if request.output_file else output_dir / "normalized.xlsx"

    logs_dir = request.logs_dir
    logs_dir_resolved = Path(logs_dir).resolve() if logs_dir else None
    logs_file = Path(request.logs_file).resolve() if request.logs_file else (
        logs_dir_resolved / "engine_events.ndjson" if logs_dir_resolved else None
    )

    normalized = RunRequest(
        config_package=config_package,
        manifest_path=Path(request.manifest_path).resolve() if request.manifest_path else None,
        input_file=input_file,
        input_sheets=list(request.input_sheets) if request.input_sheets else None,
        output_dir=output_dir,
        output_file=output_file,
        logs_dir=logs_dir_resolved,
        logs_file=logs_file,
        metadata=dict(request.metadata) if request.metadata else {},
    )
    return normalized, output_dir, output_file, logs_dir_resolved, logs_file, config_sys_path


def _ensure_dirs(output_dir: Path, logs_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)


def _input_file_name(request: RunRequest) -> str:
    return Path(request.input_file).name if request.input_file else ""


@dataclass(slots=True)
class _EngineExecutionState:
    """Container for a single engine run's mutable state."""

    normalized_request: RunRequest
    output_dir: Path
    logs_dir: Path
    run_ctx: RunContext
    runtime: ConfigRuntime
    event_emitter: EngineEventEmitter
    config_event_emitter: ConfigEventEmitter
    run_logger: logging.Logger
    summary_aggregator: SummaryAggregator | None
    input_file_name: str


def _finalize_and_emit_summaries(
    summary_aggregator: SummaryAggregator | None,
    *,
    status: RunStatus,
    failure: RunError | None,
    completed_at: datetime | None,
    output_path: str | None,
    processed_file: str | None,
    event_emitter: EngineEventEmitter | None,
    logger: logging.Logger | None,
) -> RunSummary | None:
    """Run ``SummaryAggregator.finalize`` and emit the resulting events."""

    if summary_aggregator is None:
        return None

    try:
        sheet_summaries, file_summaries, run_summary = summary_aggregator.finalize(
            status=status,
            failure=failure,
            completed_at=completed_at,
            output_path=output_path,
            processed_file=processed_file,
        )
    except Exception as exc:  # pragma: no cover - defensive
        if logger:
            logger.exception("Failed to finalize run summaries", exc_info=exc)
        return None

    if event_emitter:
        for sheet_summary in sheet_summaries:
            event_emitter.sheet_summary(sheet_summary)
        for file_summary in file_summaries:
            event_emitter.file_summary(file_summary)
        if run_summary:
            event_emitter.run_summary(run_summary)

    return run_summary


class Engine:
    """Primary runtime entrypoint."""

    def __init__(self, *, telemetry: TelemetryConfig | None = None, engine_info: EngineInfo | None = None) -> None:
        self.telemetry = telemetry or TelemetryConfig()
        self.engine_info = engine_info or EngineInfo(name="ade-engine", version="1.6.1")
        self.logger = logging.getLogger(__name__)

    def run(self, request: RunRequest | None = None, **kwargs: Any) -> RunResult:
        req = request or RunRequest(**kwargs)
        phase: RunPhase | None = RunPhase.INITIALIZATION
        normalized_tables: list[Any] = []
        output_path: Path | None = None
        processed_file: str | None = None
        state: _EngineExecutionState | None = None

        try:
            phase = RunPhase.LOAD_CONFIG
            state = self._prepare_execution(req)

            # Engine-level start event (API may later wrap with additional context).
            state.event_emitter.start(
                engine_version=self.engine_info.version,
                config_version=state.runtime.manifest.model.version,
            )

            phase = RunPhase.HOOKS
            run_hooks(
                HookStage.ON_RUN_START,
                state.runtime.hooks,
                run=state.run_ctx,
                input_file_name=state.input_file_name,
                manifest=state.runtime.manifest,
                tables=None,
                workbook=None,
                result=None,
                logger=state.run_logger,
                event_emitter=state.config_event_emitter,
            )

            def mark_phase(new_phase: RunPhase) -> None:
                nonlocal phase
                phase = new_phase

            phase = RunPhase.EXTRACTING
            normalized_tables, output_path, processed_file = execute_pipeline(
                request=state.normalized_request,
                run=state.run_ctx,
                runtime=state.runtime,
                logger=state.run_logger,
                event_emitter=state.event_emitter,
                input_file_name=state.input_file_name,
                summary_aggregator=state.summary_aggregator,
                config_event_emitter=state.config_event_emitter,
                on_phase_change=mark_phase,
            )

            phase = RunPhase.COMPLETED
            state.run_ctx.completed_at = datetime.now(timezone.utc)
            output_path_str = str(output_path) if output_path else None
            provisional = RunResult(
                status=RunStatus.SUCCEEDED,
                error=None,
                run_id=state.run_ctx.run_id,
                output_path=output_path,
                logs_dir=state.logs_dir,
                processed_file=processed_file,
            )

            phase = RunPhase.HOOKS
            run_hooks(
                HookStage.ON_RUN_END,
                state.runtime.hooks,
                run=state.run_ctx,
                input_file_name=state.input_file_name,
                manifest=state.runtime.manifest,
                tables=normalized_tables,
                workbook=None,
                result=provisional,
                logger=state.run_logger,
                event_emitter=state.config_event_emitter,
            )

            _finalize_and_emit_summaries(
                state.summary_aggregator,
                status=RunStatus.SUCCEEDED,
                failure=None,
                completed_at=state.run_ctx.completed_at,
                output_path=output_path_str,
                processed_file=processed_file,
                event_emitter=state.event_emitter,
                logger=self.logger,
            )
            state.event_emitter.complete(
                status="succeeded",
                output_path=output_path_str,
                processed_file=processed_file,
            )

            return provisional

        except Exception as exc:  # pragma: no cover - exercised via tests
            error: RunError = error_to_run_error(exc, stage=phase)
            self.logger.exception("Run failed", exc_info=exc)
            return self._handle_failure(
                state=state,
                error=error,
                output_path=output_path,
                processed_file=processed_file,
                exc=exc,
            )

    def _prepare_execution(self, request: RunRequest) -> _EngineExecutionState:
        normalized_request, output_dir, output_file, logs_dir, logs_file, config_sys_path = _resolve_paths(request)

        metadata = dict(normalized_request.metadata) if normalized_request.metadata else {}
        run_id = _coerce_uuid(metadata.get("run_id")) or uuid7()

        _ensure_dirs(output_file.parent, logs_dir or output_file.parent)
        assert normalized_request.input_file is not None
        input_file_name = _input_file_name(normalized_request)

        if config_sys_path:
            sys_path_entry = str(config_sys_path)
            if sys_path_entry not in sys.path:
                sys.path.insert(0, sys_path_entry)

        run_ctx = RunContext(
            run_id=run_id,
            metadata=metadata,
            manifest=None,
            paths=RunPaths(
                input_file=normalized_request.input_file,
                output_dir=output_dir,
                output_file=output_file,
                logs_dir=logs_dir,
                logs_file=logs_file,
            ),
            started_at=datetime.now(timezone.utc),
        )

        normalized_request.output_dir = output_dir
        normalized_request.output_file = output_file
        normalized_request.logs_dir = logs_dir
        normalized_request.logs_file = logs_file

        runtime = load_config_runtime(package=normalized_request.config_package, manifest_path=normalized_request.manifest_path)
        run_ctx.manifest = runtime.manifest
        if runtime.manifest.model.script_api_version != 3:
            raise ConfigError(
                f"Config manifest declares script_api_version={runtime.manifest.model.script_api_version}; "
                "this engine requires script_api_version=3. Update ade_config call signatures to accept "
                "logger and event_emitter."
            )

        base_telemetry = self.telemetry or TelemetryConfig()
        sink_factories = list(base_telemetry.event_sink_factories)

        if logs_file:
            def _file_sink(run: RunContext) -> FileEventSink:
                assert run.paths.logs_file is not None
                run.paths.logs_file.parent.mkdir(parents=True, exist_ok=True)
                return FileEventSink(path=run.paths.logs_file, min_level=base_telemetry.min_event_level)

            sink_factories.append(_file_sink)

        telemetry_config = TelemetryConfig(
            correlation_id=base_telemetry.correlation_id,
            min_event_level=base_telemetry.min_event_level,
            event_sink_factories=sink_factories,
            stdout_sink_factory=base_telemetry.stdout_sink_factory,
        )

        event_sink = telemetry_config.build_sink(run_ctx) if telemetry_config else None
        event_emitter = EngineEventEmitter(run=run_ctx, event_sink=event_sink, source="engine")
        config_event_emitter = event_emitter.config_emitter()
        run_logger = build_run_logger(base_name="ade_engine.run", event_emitter=event_emitter, bridge_to_telemetry=True)
        summary_aggregator = SummaryAggregator(
            run=run_ctx,
            manifest=runtime.manifest,
            engine_version=self.engine_info.version,
            config_version=runtime.manifest.model.version,
        )

        return _EngineExecutionState(
            normalized_request=normalized_request,
            output_dir=output_dir,
            logs_dir=logs_dir or output_dir,
            run_ctx=run_ctx,
            runtime=runtime,
            event_emitter=event_emitter,
            config_event_emitter=config_event_emitter,
            run_logger=run_logger,
            summary_aggregator=summary_aggregator,
            input_file_name=input_file_name,
        )

    def _handle_failure(
        self,
        *,
        state: _EngineExecutionState | None,
        error: RunError,
        output_path: Path | None,
        processed_file: str | None,
        exc: Exception,
    ) -> RunResult:
        output_path_str = str(output_path) if output_path else None

        try:
            if state:
                state.run_ctx.completed_at = datetime.now(timezone.utc)
                summary_aggregator = state.summary_aggregator
                if summary_aggregator is None:
                    summary_aggregator = SummaryAggregator(
                        run=state.run_ctx,
                        manifest=state.runtime.manifest if state.runtime else None,
                        engine_version=self.engine_info.version,
                        config_version=state.runtime.manifest.model.version if state.runtime else None,
                    )

                _finalize_and_emit_summaries(
                    summary_aggregator,
                    status=RunStatus.FAILED,
                    failure=error,
                    completed_at=state.run_ctx.completed_at,
                    output_path=output_path_str,
                    processed_file=processed_file,
                    event_emitter=state.event_emitter,
                    logger=self.logger,
                )

                if state.event_emitter:
                    failure_payload = {
                        "code": error.code.value if hasattr(error, "code") else None,
                        "stage": error.stage.value if hasattr(error, "stage") and error.stage else None,
                        "message": getattr(error, "message", str(exc)),
                    }
                    state.event_emitter.complete(
                        status="failed",
                        failure=failure_payload,
                        output_path=output_path_str,
                        processed_file=processed_file,
                    )
        except Exception:
            # Telemetry failures should never mask the underlying error.
            pass

        run_id = state.run_ctx.run_id if state else uuid7()
        logs_dir = state.logs_dir if state else Path("logs")

        return RunResult(
            status=RunStatus.FAILED,
            error=error,
            run_id=run_id,
            output_path=output_path,
            logs_dir=logs_dir,
            processed_file=processed_file,
        )


__all__ = ["Engine"]
