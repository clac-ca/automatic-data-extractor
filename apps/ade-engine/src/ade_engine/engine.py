"""Engine orchestration using the Workbook → Sheet → Table pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from ade_engine.common.events import EventLogger
from ade_engine.common.logging import start_run_logging
from ade_engine.config.loader import load_config_runtime
from ade_engine.exceptions import ConfigError, HookError, InputError, PipelineError
from ade_engine.hooks.dispatcher import HookDispatcher
from ade_engine.io.paths import prepare_run_request
from ade_engine.io.workbook import WorkbookIO
from ade_engine.pipeline import (
    ColumnMapper,
    Pipeline,
    SheetLayout,
    TableDetector,
    TableExtractor,
    TableNormalizer,
    TableRenderer,
)
from ade_engine.runtime import PluginInvoker
from ade_engine.settings import Settings
from ade_engine.types.contexts import RunContext
from ade_engine.types.run import RunError, RunErrorCode, RunRequest, RunResult, RunStatus


class Engine:
    """High-level orchestration for normalization runs."""

    def __init__(
        self,
        *,
        detector: TableDetector | None = None,
        extractor: TableExtractor | None = None,
        mapper: ColumnMapper | None = None,
        normalizer: TableNormalizer | None = None,
        renderer_factory: Callable[[], TableRenderer] | None = None,
        pipeline: Pipeline | None = None,
        workbook_io: WorkbookIO | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings()

        renderer_factory = renderer_factory or (lambda: TableRenderer(layout=SheetLayout()))
        self.pipeline = pipeline or Pipeline(
            detector=detector or TableDetector(),
            extractor=extractor or TableExtractor(),
            mapper=mapper or ColumnMapper(),
            normalizer=normalizer or TableNormalizer(),
            renderer_factory=renderer_factory,
        )
        self.workbook_io = workbook_io or WorkbookIO()

    def run(
        self,
        request: RunRequest | None = None,
        *,
        logger: logging.Logger | logging.LoggerAdapter | None = None,
        events: EventLogger | None = None,
        **kwargs: Any,
    ) -> RunResult:
        """Execute a single run."""
        req = request or RunRequest(**kwargs)

        logger = logger or logging.getLogger(__name__)
        engine_events = events or EventLogger(logger, namespace="engine")
        config_events = EventLogger(logger, namespace="engine.config")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Run starting",
                extra={
                    "data": {
                        "config_package": req.config_package,
                        "input_file": str(req.input_file) if req.input_file else None,
                        "output_dir": str(req.output_dir) if req.output_dir else None,
                        "logs_dir": str(req.logs_dir) if req.logs_dir else None,
                    },
                },
            )

        status = RunStatus.RUNNING
        error: RunError | None = None

        output_path: Path | None = None
        processed_file: str | None = None
        output_dir: Path | None = None
        logs_dir: Path | None = None

        started_at = datetime.now(timezone.utc)
        completed_at: datetime = started_at

        engine_events.emit(
            "run.started",
            message="Run started",
            input_file=str(req.input_file) if req.input_file else None,
            config_package=req.config_package,
        )

        try:
            prepared = prepare_run_request(req, default_config_package=self.settings.config_package)

            output_dir = prepared.output_dir
            logs_dir = prepared.logs_dir
            input_path = prepared.request.input_file
            if input_path is None:
                raise InputError("RunRequest.input_file is required")

            processed_file = input_path.name
            output_path = prepared.output_file

            output_dir.mkdir(parents=True, exist_ok=True)
            if logs_dir:
                logs_dir.mkdir(parents=True, exist_ok=True)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Resolved run paths",
                    extra={
                        "data": {
                            "input_file": str(input_path),
                            "output_file": str(output_path),
                            "output_dir": str(output_dir),
                            "logs_file": str(prepared.logs_file) if prepared.logs_file else None,
                            "logs_dir": str(logs_dir) if logs_dir else None,
                        },
                    },
                )

            engine_events.emit(
                "run.planned",
                message="Prepared run request",
                output_file=str(prepared.output_file),
                output_dir=str(prepared.output_dir),
                logs_file=str(prepared.logs_file) if prepared.logs_file else None,
                logs_dir=str(prepared.logs_dir) if prepared.logs_dir else None,
            )

            prepared.resolved_config.ensure_on_sys_path()

            runtime = load_config_runtime(
                package=prepared.resolved_config,
                manifest_path=prepared.request.manifest_path,
            )

            engine_events.emit(
                "config.loaded",
                message="Config loaded",
                config_package=runtime.package.__name__,
                manifest_version=runtime.manifest.model.version,
                manifest_schema=runtime.manifest.model.schema_id,
                script_api_version=runtime.manifest.model.script_api_version,
            )

            with self.workbook_io.open_source(Path(input_path)) as source_wb:
                output_wb = self.workbook_io.create_output()

                run_ctx = RunContext(
                    source_path=input_path,
                    output_path=prepared.output_file,
                    manifest=runtime.manifest,
                    source_workbook=source_wb,
                    output_workbook=output_wb,
                    state={},
                    logger=logger,
                    events=config_events,
                )

                invoker = PluginInvoker(runtime=runtime, run=run_ctx, logger=logger, events=config_events)
                hooks = HookDispatcher(runtime.hooks, invoker=invoker, logger=logger)

                engine_events.emit(
                    "workbook.started",
                    message="Workbook processing started",
                    sheet_count=len(getattr(source_wb, "worksheets", [])),
                )

                hooks.on_workbook_start(run_ctx)

                sheet_names = self.workbook_io.resolve_sheet_names(source_wb, prepared.request.input_sheets)
                sheet_index_lookup = {ws.title: idx for idx, ws in enumerate(source_wb.worksheets)}
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Processing sheets",
                        extra={
                            "data": {
                                "sheet_names": sheet_names,
                                "input_sheets_filter": prepared.request.input_sheets,
                                "sheet_count": len(sheet_names),
                            },
                        },
                    )

                for sheet_position, sheet_name in enumerate(sheet_names):
                    self.pipeline.process_sheet(
                        runtime=runtime,
                        run_ctx=run_ctx,
                        hook_dispatcher=hooks,
                        invoker=invoker,
                        source_wb=source_wb,
                        output_wb=output_wb,
                        sheet_name=sheet_name,
                        sheet_position=sheet_position,
                        sheet_index_lookup=sheet_index_lookup,
                        logger=logger,
                    )

                hooks.on_workbook_before_save(run_ctx)

                self.workbook_io.save_output(output_wb, prepared.output_file)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Output workbook saved",
                        extra={
                            "data": {
                                "output_file": str(prepared.output_file),
                                "logs_dir": str(logs_dir) if logs_dir else None,
                            },
                        },
                    )

            status = RunStatus.SUCCEEDED

        except (ConfigError, InputError, HookError, PipelineError) as exc:
            status = RunStatus.FAILED
            if isinstance(exc, ConfigError):
                code = RunErrorCode.CONFIG_ERROR
            elif isinstance(exc, InputError):
                code = RunErrorCode.INPUT_ERROR
            elif isinstance(exc, HookError):
                code = RunErrorCode.HOOK_ERROR
            else:
                code = RunErrorCode.PIPELINE_ERROR

            logger.error("%s: %s", code.value, exc)
            error = RunError(code=code, stage=None, message=str(exc))

        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Engine run failed", exc_info=exc)
            status = RunStatus.FAILED
            error = RunError(code=RunErrorCode.UNKNOWN_ERROR, stage=None, message=str(exc))

        finally:
            completed_at = datetime.now(timezone.utc)
            started_at_str = started_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            completed_at_str = completed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

            engine_events.emit(
                "run.completed",
                message="Run completed",
                status=status.value,
                stage=None,
                output_path=str(output_path) if output_path else None,
                error=(
                    {"code": error.code.value, "stage": error.stage, "message": error.message}
                    if error
                    else None
                ),
                started_at=started_at_str,
                completed_at=completed_at_str,
            )

        result_logs_dir = logs_dir or output_dir or Path(".")
        return RunResult(
            status=status,
            error=error,
            output_path=output_path,
            logs_dir=result_logs_dir,
            processed_file=processed_file,
            started_at=started_at,
            completed_at=completed_at,
        )


@dataclass(frozen=True)
class ExecutedRun:
    """Bundle of run output info for the CLI/batch layer."""

    input_file: Path
    output_file: Path
    logs_file: Path | None
    result: RunResult


def _log_file_name(log_format: str) -> str:
    """Return the default log file name for a given log format."""
    return "engine_events.ndjson" if log_format == "ndjson" else "engine.log"


def run_inputs(
    inputs: Iterable[Path],
    *,
    config_package: str,
    output_dir: Path | None = None,
    logs_dir: Path | None = None,
    log_format: str | None = None,
    log_level: int | None = None,
    input_sheets: list[str] | None = None,
) -> list[ExecutedRun]:
    """Run the engine for multiple input files."""

    default_settings = Settings()

    resolved_log_format = str(log_format or default_settings.log_format or "text").strip().lower()
    if resolved_log_format not in {"text", "ndjson"}:
        raise ValueError("log_format must be 'text' or 'ndjson'")

    input_paths = [Path(path).resolve() for path in inputs]
    if not input_paths:
        raise InputError("At least one input file is required")

    resolved_output_dir = Path(output_dir or Path("output")).resolve()
    resolved_logs_dir = Path(logs_dir).resolve() if logs_dir else None

    effective_log_level = log_level if log_level is not None else default_settings.log_level

    engine_settings = Settings(
        config_package=config_package,
        log_level=effective_log_level,
        log_format=resolved_log_format,
    )
    engine = Engine(settings=engine_settings)

    results: list[ExecutedRun] = []

    for idx, input_file in enumerate(input_paths):
        output_file = (resolved_output_dir / f"{input_file.stem}_normalized.xlsx").resolve()
        logs_file = (
            (resolved_logs_dir / f"{input_file.stem}_{_log_file_name(resolved_log_format)}").resolve()
            if resolved_logs_dir
            else None
        )

        request = RunRequest(
            config_package=config_package,
            input_file=input_file,
            input_sheets=list(input_sheets) if input_sheets else None,
            output_dir=resolved_output_dir,
            output_file=output_file,
            logs_dir=resolved_logs_dir,
            logs_file=logs_file,
        )

        with start_run_logging(
            log_format=resolved_log_format,
            enable_console_logging=True,
            log_file=logs_file,
            log_level=effective_log_level,
        ) as log_ctx:
            if log_ctx.logger.isEnabledFor(logging.DEBUG):
                log_ctx.logger.debug(
                    "Engine run planned",
                    extra={
                        "data": {
                            "sequence": {"current": idx + 1, "total": len(input_paths)},
                            "input_file": str(input_file),
                            "output_file": str(output_file),
                            "logs_file": str(logs_file) if logs_file else None,
                            "log_format": resolved_log_format,
                            "log_level": logging.getLevelName(effective_log_level),
                            "input_sheets": list(input_sheets) if input_sheets else None,
                        },
                    },
                )
            result = engine.run(request, logger=log_ctx.logger, events=log_ctx.events)
            if log_ctx.logger.isEnabledFor(logging.DEBUG):
                log_ctx.logger.debug(
                    "Engine run completed",
                    extra={
                        "data": {
                            "input_file": str(input_file),
                            "status": result.status.value,
                            "output_file": str(output_file),
                            "logs_file": str(logs_file) if logs_file else None,
                            "error": result.error.message if result.error else None,
                        },
                    },
                )

        results.append(
            ExecutedRun(
                input_file=input_file,
                output_file=output_file,
                logs_file=logs_file,
                result=result,
            )
        )

    return results


__all__ = ["Engine", "ExecutedRun", "run_inputs"]
