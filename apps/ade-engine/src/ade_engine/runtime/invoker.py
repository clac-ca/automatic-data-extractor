"""Uniform invocation of config-provided callables with a stable kwarg set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ade_engine.config.loader import ConfigRuntime
from ade_engine.types.contexts import RunContext


@dataclass(frozen=True)
class PluginInvoker:
    runtime: ConfigRuntime
    run: RunContext
    logger: Any
    events: Any

    def base_kwargs(self) -> dict[str, Any]:
        input_file_name = self.run.source_path.name
        # Provide a stable set of kwargs for all config callables; scripts must accept **_.
        return {
            "run": self.run,
            "state": self.run.state,
            "manifest": self.runtime.manifest,
            "logger": self.logger,
            "events": self.events,
            # Backwards compatibility for existing config callables
            "event_emitter": self.events,
            "input_file_name": input_file_name,
        }

    def call(self, fn: Callable[..., Any], /, **kwargs: Any) -> Any:
        payload = self.base_kwargs()
        payload.update(kwargs)
        return fn(**payload)


__all__ = ["PluginInvoker"]
