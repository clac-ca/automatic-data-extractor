"""Hook registry for lifecycle callbacks defined in the manifest."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum
from types import ModuleType
from typing import Any, Callable

from openpyxl import Workbook

from ade_engine.core.errors import ConfigError
from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import MappedTable, NormalizedTable, ExtractedTable, RunContext, RunResult
from ade_engine.infra.telemetry import PipelineLogger


class HookStage(str, Enum):
    """Lifecycle hook stages defined by the engine."""

    ON_RUN_START = "on_run_start"
    ON_AFTER_EXTRACT = "on_after_extract"
    ON_AFTER_MAPPING = "on_after_mapping"
    ON_BEFORE_SAVE = "on_before_save"
    ON_RUN_END = "on_run_end"


@dataclass
class HookContext:
    """Context passed to hook functions."""

    run: RunContext
    state: dict[str, Any]
    manifest: ManifestContext
    tables: list[ExtractedTable | MappedTable | NormalizedTable] | None
    workbook: Workbook | None
    result: RunResult | None
    logger: PipelineLogger
    stage: HookStage


class HookRegistry(dict[HookStage, list[Callable[..., Any]]]):
    """Mapping of hook stage to ordered callables."""

    @classmethod
    def from_manifest(cls, *, package: ModuleType, manifest: ManifestContext) -> "HookRegistry":
        registry = cls()
        hooks = manifest.hooks
        for stage in HookStage:
            configured = getattr(hooks, stage.value)
            callables: list[Callable[..., Any]] = []
            for module_path in configured:
                import_path = f"{package.__name__}.{module_path}"
                try:
                    module = importlib.import_module(import_path)
                except ModuleNotFoundError as exc:  # pragma: no cover - exercised via ConfigError
                    raise ConfigError(f"Hook module '{import_path}' not found") from exc

                entrypoint = getattr(module, "run", None)
                if entrypoint is None:
                    entrypoint = getattr(module, "main", None)
                if entrypoint is None or not callable(entrypoint):
                    raise ConfigError(f"Hook module '{import_path}' is missing a callable entrypoint")

                callables.append(entrypoint)

            registry[stage] = callables

        return registry
