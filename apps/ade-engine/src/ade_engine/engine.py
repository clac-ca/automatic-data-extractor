"""Engine orchestration using the Workbook → Sheet → Table pipeline."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from ade_engine.config.loader import load_config_runtime
from ade_engine.events import NULL_EVENT_EMITTER
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
from ade_engine.runtime import PluginInvoker, StageTracker
from ade_engine.settings import Settings
from ade_engine.types.contexts import RunContext
from ade_engine.types.run import RunError, RunErrorCode, RunRequest, RunResult, RunStatus


_PIPELINE_STAGE_PREFIXES = ("detect[", "extract[", "map[", "normalize[", "render[", "sheet[")


def _classify_unknown(stage: str) -> RunErrorCode:
    if stage.startswith("hooks."):
        return RunErrorCode.HOOK_ERROR
    if stage.startswith(_PIPELINE_STAGE_PREFIXES):
        return RunErrorCode.PIPELINE_ERROR
    return RunErrorCode.UNKNOWN_ERROR


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
        emitter = event_emitter or NULL_EVENT_EMITTER
        stage = StageTracker("prepare")

        status = RunStatus.RUNNING
        error: RunError | None = None

        output_path: Path | None = None
        processed_file: str | None = None
        output_dir: Path | None = None
        logs_dir: Path | None = None

        started_at = datetime.utcnow()
        completed_at: datetime | None = None

        emitter.emit(
            "run.started",
            message="Run started",
            input_file=str(req.input_file) if req.input_file else None,
            config_package=req.config_package,
        )

        try:
            stage.set("prepare_request")
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

            stage.set("load_config")
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

            stage.set("open_workbook")
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
                hooks = HookDispatcher(runtime.hooks, invoker=invoker, stage=stage, logger=logger_obj)

                emitter.emit(
                    "workbook.started",
                    message="Workbook processing started",
                    sheet_count=len(getattr(source_wb, "worksheets", [])),
                )

                stage.set("hooks.on_workbook_start")
                hooks.on_workbook_start(run_ctx)

                stage.set("resolve_sheets")
                sheet_names = self.workbook_io.resolve_sheet_names(source_wb, prepared.request.input_sheets)
                sheet_index_lookup = {ws.title: idx for idx, ws in enumerate(source_wb.worksheets)}

                for sheet_position, sheet_name in enumerate(sheet_names):
                    self.pipeline.process_sheet(
                        runtime=runtime,
                        run_ctx=run_ctx,
                        hook_dispatcher=hooks,
                        invoker=invoker,
                        stage=stage,
                        source_wb=source_wb,
                        output_wb=output_wb,
                        sheet_name=sheet_name,
                        sheet_position=sheet_position,
                        sheet_index_lookup=sheet_index_lookup,
                        logger=logger_obj,
                    )

                stage.set("hooks.on_workbook_before_save")
                hooks.on_workbook_before_save(run_ctx)

                stage.set("save_output")
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
            logger_obj.error("%s at stage=%s: %s", code.value, stage.value, exc)
            error = RunError(code=code, stage=stage.value, message=str(exc))

        except Exception as exc:
            logger_obj.exception("Engine run failed at stage=%s", stage.value, exc_info=exc)
            status = RunStatus.FAILED
            error = RunError(code=_classify_unknown(stage.value), stage=stage.value, message=str(exc))

        finally:
            completed_at = datetime.utcnow()
            emitter.emit(
                "run.completed",
                message="Run completed",
                status=status.value,
                stage=stage.value,
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


__all__ = ["Engine"]
