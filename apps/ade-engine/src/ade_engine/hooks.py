"""Hook loading and execution utilities."""

from __future__ import annotations

from collections import defaultdict
from importlib import import_module
from typing import Any, Callable, Mapping

from .model import JobContext
from .sinks import ArtifactSink


class HookLoadError(RuntimeError):
    """Raised when hooks cannot be imported from ``ade_config``."""


class HookExecutionError(RuntimeError):
    """Raised when a hook fails while the job is running."""


class HookRegistry:
    """Resolve and execute hooks declared in the manifest."""

    _VALID_STAGES = {
        "on_activate",
        "on_job_start",
        "on_after_extract",
        "on_before_save",
        "on_job_end",
    }

    def __init__(self, manifest: Mapping[str, Any], *, package: str) -> None:
        hooks_section = manifest.get("hooks") or {}
        resolved: dict[str, list[Callable[..., Any]]] = defaultdict(list)

        for stage, entries in hooks_section.items():
            if stage not in self._VALID_STAGES:
                continue
            if not isinstance(entries, list):
                raise HookLoadError(
                    f"Hook stage '{stage}' must be a list of hook entries"
                )
            for entry in entries:
                if not entry.get("enabled", True):
                    continue
                script = entry.get("script")
                if not script:
                    continue
                module_name = _script_to_module(script, package=package)
                try:
                    module = import_module(module_name)
                except ModuleNotFoundError as exc:  # pragma: no cover - import guard
                    raise HookLoadError(
                        f"Hook module '{module_name}' could not be imported"
                    ) from exc

                func = getattr(module, "run", None) or getattr(module, "main", None)
                if func is None:
                    raise HookLoadError(
                        f"Hook module '{module_name}' must expose a 'run' or 'main' callable"
                    )
                resolved[stage].append(func)

        self._hooks = {stage: tuple(funcs) for stage, funcs in resolved.items()}

    def call(self, stage: str, *, job: JobContext, artifact: ArtifactSink, **ctx: Any) -> None:
        functions = self._hooks.get(stage)
        if not functions:
            return
        for func in functions:
            try:
                func(job=job, artifact=artifact, **ctx)
            except Exception as exc:  # pragma: no cover - hook failure path
                raise HookExecutionError(
                    f"Hook '{func.__module__}.{func.__name__}' failed during {stage}: {exc}"
                ) from exc


def _script_to_module(script: str, *, package: str) -> str:
    module = script[:-3] if script.endswith(".py") else script
    module = module.replace("/", ".").replace("-", "_")
    return f"{package}.{module}" if not module.startswith(package) else module

__all__ = ["HookExecutionError", "HookLoadError", "HookRegistry"]
