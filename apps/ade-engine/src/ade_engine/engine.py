from __future__ import annotations

import logging
import sys
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List

from ade_engine.exceptions import ConfigError, HookError, InputError, PipelineError
from ade_engine.io.workbook import (
    create_output_workbook,
    open_source_workbook,
    resolve_sheet_names,
)
from ade_engine.logging import create_run_logger_context
from ade_engine.pipeline import Pipeline
from ade_engine.registry import Registry
from ade_engine.registry.models import HookName
from ade_engine.settings import Settings
from ade_engine.types.run import RunError, RunErrorCode, RunRequest, RunResult, RunStatus
from ade_engine.io.paths import PreparedRun, prepare_run_request
from ade_engine.logging import RunLogger


@dataclass
class ExecutedRun:
    request: RunRequest
    result: RunResult


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
    @staticmethod
    def _coerce_config_package_path(path: Path) -> tuple[str, str]:
        """Resolve a filesystem path to an importable package name and sys.path root.

        Supports passing either:
        - the package directory itself (e.g., /tmp/pkg/ade_config)
        - a project root containing ``src/<package>`` (common for editable installs)
        - a project root containing ``ade_config`` directly

        Returns (package_name, sys_path_root).
        """

        path = path.expanduser().resolve()
        if not path.exists():
            raise ModuleNotFoundError(f"Config package path does not exist: {path}")
        if path.is_file():
            raise ModuleNotFoundError(f"Config package path must be a directory: {path}")

        # Case 1: path points directly at a package directory.
        if (path / "__init__.py").is_file() and path.name.isidentifier():
            return path.name, str(path.parent)

        # Case 2: src layout (prefer ade_config if present).
        src_dir = path / "src"
        if src_dir.is_dir():
            packages = [
                p for p in src_dir.iterdir() if p.is_dir() and (p / "__init__.py").is_file()
            ]
            packages = sorted(packages, key=lambda p: (p.name != "ade_config", p.name))
            if packages:
                chosen = packages[0]
                return chosen.name, str(src_dir.resolve())

        # Case 3: flat layout with ade_config under the root.
        ade_pkg = path / "ade_config"
        if ade_pkg.is_dir() and (ade_pkg / "__init__.py").is_file():
            return "ade_config", str(path)

        raise ModuleNotFoundError(f"Could not locate a Python package under {path}")

    def _load_registry(self, *, config_package: Path, logger: RunLogger) -> Registry:
        """Create a Registry and populate it using a config package entrypoint."""

        registry = Registry()
        resolved_package, resolved_root = self._coerce_config_package_path(Path(config_package))

        root_path = Path(resolved_root).expanduser().resolve()
        if str(root_path) not in sys.path:
            sys.path.insert(0, str(root_path))

        entrypoint = None
        pkg = importlib.import_module(resolved_package)
        register_fn = getattr(pkg, "register", None)

        if callable(register_fn):
            entrypoint = f"{resolved_package}.register"
            register_fn(registry)
        else:
            raise ModuleNotFoundError(
                f"Config package '{resolved_package}' must define a register(registry) entrypoint"
            )

        registry.finalize()
        logger.event(
            "config.loaded",
            message="Config package loaded",
            data={
                "config_package": resolved_package,
                "config_path": str(root_path),
                "entrypoint": entrypoint,
                "fields": list(registry.fields.keys()),
                "settings": self._settings_snapshot(),
            },
        )
        return registry

    # ------------------------------------------------------------------
    def run(self, request: RunRequest | None = None, *, logger: RunLogger | None = None, **kwargs: Any) -> RunResult:
        req = request or RunRequest(**kwargs)
        prepared: PreparedRun = prepare_run_request(req)

        logs_dir = prepared.logs_dir or prepared.output_dir
        if prepared.output_dir:
            prepared.output_dir.mkdir(parents=True, exist_ok=True)
        if logs_dir:
            logs_dir.mkdir(parents=True, exist_ok=True)

        # If the caller only provided --logs-dir (common for the CLI),
        # derive a per-input log file name that matches the selected format.
        log_file = prepared.logs_file
        if log_file is None and logs_dir is not None and prepared.request.input_file:
            suffix = "engine_events.ndjson" if self.settings.log_format == "ndjson" else "engine.log"
            log_file = (logs_dir / f"{Path(prepared.request.input_file).stem}_{suffix}").resolve()

        with create_run_logger_context(
            log_format=self.settings.log_format,
            log_level=self.settings.log_level,
            log_file=log_file,
        ) as log_ctx:
            run_logger: RunLogger = log_ctx.logger

            run_logger.event(
                "settings.effective",
                message="Effective engine settings",
                level=logging.DEBUG,
                data={"settings": self._settings_snapshot()},
            )

            run_metadata = {
                "input_file": str(prepared.request.input_file),
                "output_file": str(prepared.output_file),
            }
            status = RunStatus.RUNNING
            error: RunError | None = None
            state: dict = {}
            try:
                registry = self._load_registry(
                    config_package=prepared.request.config_package,
                    logger=run_logger,
                )
                pipeline = Pipeline(registry=registry, settings=self.settings, logger=run_logger)

                with open_source_workbook(Path(prepared.request.input_file)) as source_wb:
                    output_wb = create_output_workbook()

                    # Hooks: workbook start
                    registry.run_hooks(
                        HookName.ON_WORKBOOK_START,
                        state=state,
                        run_metadata=run_metadata,
                        workbook=source_wb,
                        sheet=None,
                        table=None,
                        logger=run_logger,
                    )

                    sheet_names = resolve_sheet_names(source_wb, prepared.request.input_sheets)
                    for sheet_name in sheet_names:
                        sheet = source_wb[sheet_name]
                        out_sheet = output_wb.create_sheet(title=sheet_name)

                        registry.run_hooks(
                            HookName.ON_SHEET_START,
                            state=state,
                            run_metadata=run_metadata,
                            workbook=source_wb,
                            sheet=sheet,
                            table=None,
                            logger=run_logger,
                        )

                        pipeline.process_sheet(
                            sheet=sheet,
                            output_sheet=out_sheet,
                            state=state,
                            run_metadata=run_metadata,
                        )

                    registry.run_hooks(
                        HookName.ON_WORKBOOK_BEFORE_SAVE,
                        state=state,
                        run_metadata=run_metadata,
                        workbook=output_wb,
                        sheet=None,
                        table=None,
                        logger=run_logger,
                    )
                    output_wb.save(prepared.output_file)

                status = RunStatus.SUCCEEDED
            except (ConfigError, InputError, HookError, PipelineError) as exc:
                status = RunStatus.FAILED
                code_lookup = {
                    ConfigError: RunErrorCode.CONFIG_ERROR,
                    InputError: RunErrorCode.INPUT_ERROR,
                    HookError: RunErrorCode.HOOK_ERROR,
                    PipelineError: RunErrorCode.PIPELINE_ERROR,
                }
                code = next((val for exc_type, val in code_lookup.items() if isinstance(exc, exc_type)), RunErrorCode.PIPELINE_ERROR)
                error = RunError(code=code, stage=getattr(exc, "stage", None), message=str(exc))
                run_logger.exception("Run failed", exc_info=exc)
            except Exception as exc:
                status = RunStatus.FAILED
                error = RunError(code=RunErrorCode.UNKNOWN_ERROR, stage=None, message=str(exc))
                run_logger.exception("Run failed", exc_info=exc)
            return RunResult(
                status=status,
                error=error,
                output_path=prepared.output_file if status == RunStatus.SUCCEEDED else None,
                logs_dir=logs_dir,
                processed_file=prepared.request.input_file.name if prepared.request.input_file else None,
            )


# Convenience helper

def run_inputs(
    inputs: Iterable[Path],
    *,
    config_package: Path,
    output_dir: Path | None = None,
    logs_dir: Path | None = None,
    log_format: str | None = None,
    log_level: int | None = None,
    input_sheets: list[str] | None = None,
) -> List[ExecutedRun]:
    config_package_path = Path(config_package).expanduser().resolve()
    base_settings = Settings()
    effective_settings = Settings(
        log_format=log_format or base_settings.log_format,
        log_level=log_level or base_settings.log_level,
    )
    engine = Engine(settings=effective_settings)
    executed: List[ExecutedRun] = []
    for input_path in inputs:
        req = RunRequest(
            config_package=config_package_path,
            input_file=input_path,
            input_sheets=input_sheets,
            output_dir=output_dir or Path.cwd() / "output",
            logs_dir=logs_dir or Path.cwd() / "logs",
        )
        result = engine.run(req)
        executed.append(ExecutedRun(request=req, result=result))
    return executed


__all__ = ["Engine", "ExecutedRun", "run_inputs"]
