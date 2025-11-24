"""Typed hook registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from typing import Any, Callable, Iterable, Mapping
import inspect

from ade_engine.core.manifest import HookCollection, ManifestContext, ScriptRef
from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import FileExtraction
from ade_engine.plugins.utils import _script_to_module
from ade_engine.sinks import ArtifactSink, EventSink


class HookLoadError(RuntimeError):
    """Raised when hooks cannot be imported from ``ade_config``."""


class HookExecutionError(RuntimeError):
    """Raised when a hook fails while the job is running."""


class HookStage(str, Enum):
    ON_ACTIVATE = "on_activate"
    ON_JOB_START = "on_job_start"
    ON_AFTER_EXTRACT = "on_after_extract"
    ON_BEFORE_SAVE = "on_before_save"
    ON_JOB_END = "on_job_end"


@dataclass(slots=True)
class HookContext:
    job: JobContext
    artifact: ArtifactSink
    events: EventSink | None = None
    tables: list[FileExtraction] | None = None
    result: Any | None = None


class HookRegistry:
    """Resolve and execute hooks declared in the manifest."""

    def __init__(self, manifest: ManifestContext, *, package: str) -> None:
        self._hooks: dict[HookStage, tuple[tuple[str, str], ...]] = {}
        entries = self._load_entries(manifest)
        for stage, refs in entries.items():
            funcs: list[tuple[str, str]] = []
            for ref in refs:
                script = ref.script if isinstance(ref, ScriptRef) else ref.get("script")
                enabled = ref.enabled if isinstance(ref, ScriptRef) else ref.get("enabled", True)
                if not enabled or not script:
                    continue
                module_name = _script_to_module(script, package=package)
                try:
                    module = import_module(module_name)
                except ModuleNotFoundError as exc:  # pragma: no cover - import guard
                    raise HookLoadError(
                        f"Hook module '{module_name}' could not be imported"
                    ) from exc

                func_name = "run" if hasattr(module, "run") else "main" if hasattr(module, "main") else None
                if func_name is None:
                    raise HookLoadError(
                        f"Hook module '{module_name}' must expose a 'run' or 'main' callable"
                    )
                funcs.append((module_name, func_name))
            if funcs:
                self._hooks[stage] = tuple(funcs)

    def _load_entries(
        self, manifest: ManifestContext
    ) -> Mapping[HookStage, Iterable[ScriptRef | Mapping[str, Any]]]:
        if manifest.model is not None and isinstance(manifest.model.hooks, HookCollection):
            hooks = manifest.model.hooks
            return {
                HookStage.ON_ACTIVATE: hooks.on_activate,
                HookStage.ON_JOB_START: hooks.on_job_start,
                HookStage.ON_AFTER_EXTRACT: hooks.on_after_extract,
                HookStage.ON_BEFORE_SAVE: hooks.on_before_save,
                HookStage.ON_JOB_END: hooks.on_job_end,
            }

        hooks_raw = (manifest.raw.get("hooks") if isinstance(manifest.raw, Mapping) else {}) or {}
        results: dict[HookStage, Iterable[Mapping[str, Any]]] = {}
        for stage in HookStage:
            entries = hooks_raw.get(stage.value)
            if isinstance(entries, list):
                results[stage] = entries
        return results

    def call(self, stage: HookStage, ctx: HookContext) -> None:
        functions = self._hooks.get(stage)
        if not functions:
            return
        for module_name, func_name in functions:
            try:
                module = import_module(module_name)
                func = getattr(module, func_name)
                self._invoke(func, ctx)
            except Exception as exc:  # pragma: no cover - hook failure path
                raise HookExecutionError(
                    f"Hook '{func.__module__}.{func.__name__}' failed during {stage.value}: {exc}"
                ) from exc

    def _invoke(self, func: Callable[..., Any], ctx: HookContext) -> None:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        if len(params) == 1 and params[0].kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            result = func(ctx)
        else:
            result = func(
            job=ctx.job,
            artifact=ctx.artifact,
            events=ctx.events,
            tables=ctx.tables,
            result=ctx.result,
        )
        if inspect.isgenerator(result):  # ensure generator-based hooks execute
            for _ in result:
                break


__all__ = ["HookContext", "HookExecutionError", "HookLoadError", "HookRegistry", "HookStage"]
