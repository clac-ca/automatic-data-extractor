from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ade_engine.application.run_completion_report import RunCompletionReportBuilder
from ade_engine.extensions.loader import import_and_register
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.io.run_plan import RunPlan, plan_run
from ade_engine.infrastructure.io.workbook import (
    create_output_workbook,
    open_source_workbook,
    resolve_sheet_names,
)
from ade_engine.infrastructure.observability.context import create_run_logger_context
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.errors import ConfigError, HookError, InputError, PipelineError
from ade_engine.models.extension_contexts import HookName
from ade_engine.models.run import RunError, RunErrorCode, RunRequest, RunResult, RunStatus
from ade_engine.application.pipeline.pipeline import Pipeline


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Engine:
    """High-level orchestrator for a single normalization run."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def _settings_snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the current settings."""

        def _jsonify(val: Any) -> Any:
            if isinstance(val, dict):
                return {k: _jsonify(v) for k, v in val.items()}
            if isinstance(val, (list, tuple, set)):
                return [_jsonify(v) for v in val]
            if isinstance(val, Path):
                return str(val)
            return val

        raw = self.settings.model_dump(mode="python", exclude_none=True)
        return _jsonify(raw)

    # ------------------------------------------------------------------
    def load_registry(self, *, config_package: Path, logger: RunLogger) -> Registry:
        """Create a Registry and populate it using a config package entrypoint."""

        registry = Registry()
        entrypoint = import_and_register(config_package, registry=registry)
        registry.finalize()
        logger.event(
            "config.loaded",
            message="Config package loaded",
            data={
                "config_package": str(Path(config_package).expanduser().resolve()),
                "entrypoint": entrypoint,
                "fields": list(registry.fields.keys()),
                "settings": self._settings_snapshot(),
            },
        )
        return registry

    # ------------------------------------------------------------------
    def run(self, request: RunRequest, *, logger: RunLogger | None = None) -> RunResult:
        started_at = _utc_now()

        plan: RunPlan = plan_run(request, log_format=self.settings.log_format)
        plan.output_dir.mkdir(parents=True, exist_ok=True)
        plan.logs_dir.mkdir(parents=True, exist_ok=True)

        report_builder = RunCompletionReportBuilder(input_file=plan.request.input_file, settings=self.settings)

        metadata = {
            "input_file": str(plan.request.input_file),
            "output_file": str(plan.output_path),
            "input_file_name": plan.request.input_file.name,
        }

        status = RunStatus.RUNNING
        error: RunError | None = None
        state: dict[str, Any] = {}
        output_written = False

        def _execute(run_logger: RunLogger) -> None:
            nonlocal status, error, output_written

            run_logger.event(
                "settings.effective",
                message="Effective engine settings",
                level=logging.DEBUG,
                data={"settings": self._settings_snapshot()},
            )

            try:
                run_logger.event(
                    "run.started",
                    message="Run started",
                    data={
                        "input_file": str(plan.request.input_file),
                        "config_package": str(plan.request.config_package),
                    },
                )
                run_logger.event(
                    "run.planned",
                    message="Run planned",
                    data={
                        "output_file": str(plan.output_path),
                        "output_dir": str(plan.output_dir),
                        "logs_file": str(plan.logs_path) if plan.logs_path is not None else None,
                        "logs_dir": str(plan.logs_dir),
                    },
                )

                registry = self.load_registry(
                    config_package=plan.request.config_package,
                    logger=run_logger,
                )
                report_builder.set_registry(registry)
                pipeline = Pipeline(
                    registry=registry,
                    settings=self.settings,
                    logger=run_logger,
                    report_builder=report_builder,
                )

                with open_source_workbook(plan.request.input_file) as source_wb:
                    output_wb = create_output_workbook()

                    run_logger.event(
                        "workbook.started",
                        message="Workbook started",
                        data={"sheet_count": len(source_wb.sheetnames)},
                    )

                    registry.run_hooks(
                        HookName.ON_WORKBOOK_START,
                        settings=self.settings,
                        state=state,
                        metadata=metadata,
                        input_file_name=plan.request.input_file.name,
                        workbook=source_wb,
                        logger=run_logger,
                    )

                    sheet_names = resolve_sheet_names(source_wb, plan.request.input_sheets)
                    for sheet_index, sheet_name in enumerate(sheet_names):
                        sheet = source_wb[sheet_name]
                        out_sheet = output_wb.create_sheet(title=sheet_name)
                        sheet_metadata = {**metadata, "sheet_index": sheet_index}

                        run_logger.event(
                            "sheet.started",
                            message="Sheet started",
                            data={"sheet_name": sheet_name, "sheet_index": sheet_index},
                        )

                        registry.run_hooks(
                            HookName.ON_SHEET_START,
                            settings=self.settings,
                            state=state,
                            metadata=sheet_metadata,
                            input_file_name=plan.request.input_file.name,
                            workbook=source_wb,
                            sheet=sheet,
                            logger=run_logger,
                        )

                        pipeline.process_sheet(
                            sheet=sheet,
                            output_sheet=out_sheet,
                            state=state,
                            metadata=sheet_metadata,
                            input_file_name=plan.request.input_file.name,
                        )

                    registry.run_hooks(
                        HookName.ON_WORKBOOK_BEFORE_SAVE,
                        settings=self.settings,
                        state=state,
                        metadata=metadata,
                        input_file_name=plan.request.input_file.name,
                        workbook=output_wb,
                        logger=run_logger,
                    )
                    output_wb.save(plan.output_path)
                    output_written = True

                status = RunStatus.SUCCEEDED
            except (ConfigError, InputError, HookError, PipelineError) as exc:
                status = RunStatus.FAILED
                code_lookup = {
                    ConfigError: RunErrorCode.CONFIG_ERROR,
                    InputError: RunErrorCode.INPUT_ERROR,
                    HookError: RunErrorCode.HOOK_ERROR,
                    PipelineError: RunErrorCode.PIPELINE_ERROR,
                }
                code = next(
                    (val for exc_type, val in code_lookup.items() if isinstance(exc, exc_type)),
                    RunErrorCode.PIPELINE_ERROR,
                )
                error = RunError(code=code, stage=getattr(exc, "stage", None), message=str(exc))
                run_logger.exception("Run failed", exc_info=exc)
            except Exception as exc:  # pragma: no cover - defensive
                status = RunStatus.FAILED
                error = RunError(code=RunErrorCode.UNKNOWN_ERROR, stage=None, message=str(exc))
                run_logger.exception("Run failed", exc_info=exc)

        if logger is not None:
            _execute(logger)
            completed_at = _utc_now()
            payload = report_builder.build(
                run_status=status,
                started_at=started_at,
                completed_at=completed_at,
                error=error,
                output_path=plan.output_path if output_written else None,
                output_written=output_written,
            )
            # Let RunLogger validate/normalize; don't drop `null` fields pre-validation.
            logger.event("run.completed", level=logging.INFO, data=payload.model_dump(mode="python"))
        else:
            with create_run_logger_context(
                log_format=self.settings.log_format,
                log_level=self.settings.log_level,
                log_file=plan.logs_path,
            ) as log_ctx:
                _execute(log_ctx.logger)
                completed_at = _utc_now()
                payload = report_builder.build(
                    run_status=status,
                    started_at=started_at,
                    completed_at=completed_at,
                    error=error,
                    output_path=plan.output_path if output_written else None,
                    output_written=output_written,
                )
                log_ctx.logger.event(
                    "run.completed",
                    level=logging.INFO,
                    data=payload.model_dump(mode="python"),
                )

        return RunResult(
            status=status,
            error=error,
            output_path=plan.output_path if status == RunStatus.SUCCEEDED else None,
            logs_dir=plan.logs_dir,
            processed_file=plan.request.input_file.name,
            started_at=started_at,
            completed_at=completed_at,
        )


__all__ = ["Engine"]
