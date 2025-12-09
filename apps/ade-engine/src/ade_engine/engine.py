"""Engine orchestration using the Workbook → Sheet → Table pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from uuid import UUID, uuid4

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
from ade_engine.reporting import EventEmitter, build_reporting
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
        logger: logging.Logger | None = None,
        event_emitter: Any | None = None,
        **kwargs: Any,
    ) -> RunResult:
        req = request or RunRequest(**kwargs)
        run_id: UUID = req.run_id or uuid4()

        logger_obj = logger or logging.getLogger(__name__)
        emitter = event_emitter or EventEmitter(logger_obj)

        status = RunStatus.RUNNING
        error: RunError | None = None

        output_path: Path | None = None
        processed_file: str | None = None
        output_dir: Path | None = None
        logs_dir: Path | None = None

        started_at = datetime.now(timezone.utc)
        completed_at: datetime | None = None

        emitter.emit(
            "run.started",
            message="Run started",
            input_file=str(req.input_file) if req.input_file else None,
            config_package=req.config_package,
        )

        try:
            prepared = prepare_run_request(req, default_config_package=self.settings.config_package)

            output_dir = prepared.output_dir
            logs_dir = prepared.logs_dir
            processed_file = prepared.request.input_file.name
            output_path = prepared.output_file

            output_dir.mkdir(parents=True, exist_ok=True)
            if logs_dir:
                logs_dir.mkdir(parents=True, exist_ok=True)

            emitter.emit(
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

            emitter.emit(
                "config.loaded",
                message="Config loaded",
                config_package=runtime.package.__name__,
                manifest_version=runtime.manifest.model.version,
                manifest_schema=runtime.manifest.model.schema,
                script_api_version=runtime.manifest.model.script_api_version,
            )

            with self.workbook_io.open_source(Path(prepared.request.input_file)) as source_wb:
                output_wb = self.workbook_io.create_output()

                run_meta = dict(prepared.request.metadata or {})
                run_ctx = RunContext(
                    source_path=prepared.request.input_file,
                    output_path=prepared.output_file,
                    manifest=runtime.manifest,
                    source_workbook=source_wb,
                    output_workbook=output_wb,
                    state=dict(run_meta),  # backwards-compatible seed
                    meta=run_meta,
                    logger=logger_obj,
                    event_emitter=emitter,
                )

                invoker = PluginInvoker(runtime=runtime, run=run_ctx, logger=logger_obj, event_emitter=emitter)
                hooks = HookDispatcher(runtime.hooks, invoker=invoker, logger=logger_obj)

                emitter.emit(
                    "workbook.started",
                    message="Workbook processing started",
                    sheet_count=len(getattr(source_wb, "worksheets", [])),
                )

                hooks.on_workbook_start(run_ctx)

                sheet_names = self.workbook_io.resolve_sheet_names(source_wb, prepared.request.input_sheets)
                sheet_index_lookup = {ws.title: idx for idx, ws in enumerate(source_wb.worksheets)}

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
                        logger=logger_obj,
                    )

                hooks.on_workbook_before_save(run_ctx)

                self.workbook_io.save_output(output_wb, prepared.output_file)

            status = RunStatus.SUCCEEDED

        except (ConfigError, InputError, HookError, PipelineError) as exc:
            status = RunStatus.FAILED
            code = RunErrorCode.UNKNOWN_ERROR
            if isinstance(exc, ConfigError):
                code = RunErrorCode.CONFIG_ERROR
            elif isinstance(exc, InputError):
                code = RunErrorCode.INPUT_ERROR
            elif isinstance(exc, HookError):
                code = RunErrorCode.HOOK_ERROR
            elif isinstance(exc, PipelineError):
                code = RunErrorCode.PIPELINE_ERROR
            logger_obj.error("%s: %s", code.value, exc)
            error = RunError(code=code, stage=None, message=str(exc))

        except Exception as exc:
            logger_obj.exception("Engine run failed", exc_info=exc)
            status = RunStatus.FAILED
            error = RunError(code=RunErrorCode.UNKNOWN_ERROR, stage=None, message=str(exc))

        finally:
            completed_at = datetime.now(timezone.utc)
            emitter.emit(
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
                started_at=started_at.isoformat() + "Z",
                completed_at=completed_at.isoformat() + "Z",
            )

        result_logs_dir = logs_dir or output_dir or Path(".")
        return RunResult(
            status=status,
            error=error,
            run_id=run_id,
            output_path=output_path,
            logs_dir=result_logs_dir,
            processed_file=processed_file,
            started_at=started_at,
            completed_at=completed_at,
        )


@dataclass(frozen=True)
class ExecutedRun:
    """Simple bundle of run output metadata."""

    input_file: Path
    output_file: Path
    logs_file: Path | None
    result: RunResult


def _log_filename(fmt: str) -> str:
    return "engine_events.ndjson" if fmt == "ndjson" else "engine.log"


def run_inputs(
    inputs: Iterable[Path],
    *,
    config_package: str,
    output_dir: Path | None = None,
    logs_dir: Path | None = None,
    log_format: str = "text",
    input_sheets: list[str] | None = None,
    metadata: Mapping[str, str] | None = None,
) -> list[ExecutedRun]:
    """Run the engine for multiple inputs with explicit paths."""

    fmt = str(log_format or "text").strip().lower()
    if fmt not in {"text", "ndjson"}:
        raise ValueError("log_format must be 'text' or 'ndjson'")

    input_paths = [Path(path).resolve() for path in inputs]
    if not input_paths:
        raise InputError("At least one input file is required")

    resolved_output_dir = Path(output_dir or Path("output")).resolve()
    resolved_logs_dir = Path(logs_dir or Path("logs")).resolve()

    engine = Engine(settings=Settings(config_package=config_package))
    results: list[ExecutedRun] = []

    for input_file in input_paths:
        output_file = (resolved_output_dir / f"{input_file.stem}_normalized.xlsx").resolve()
        logs_file = (resolved_logs_dir / f"{input_file.stem}_{_log_filename(fmt)}").resolve()

        run_id = uuid4()
        request = RunRequest(
            run_id=run_id,
            config_package=config_package,
            input_file=input_file,
            input_sheets=list(input_sheets) if input_sheets else None,
            output_dir=resolved_output_dir,
            output_file=output_file,
            logs_dir=resolved_logs_dir,
            logs_file=logs_file,
            metadata=dict(metadata) if metadata else {},
        )

        reporter = build_reporting(fmt, run_id=str(run_id), meta=metadata, file_path=logs_file)
        result = engine.run(request, logger=reporter.logger, event_emitter=reporter.event_emitter)
        reporter.close()

        results.append(ExecutedRun(input_file=input_file, output_file=output_file, logs_file=logs_file, result=result))

    return results


__all__ = ["Engine", "ExecutedRun", "run_inputs"]
