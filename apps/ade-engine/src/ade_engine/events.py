"""Dependency-free event emitter interface + no-op implementation.

Config scripts are passed an ``event_emitter`` kwarg. When the CLI/API wants
structured output (NDJSON) it supplies a real emitter (see :mod:`ade_engine.reporting`).

The engine always accepts an emitter object with an ``emit(event, **fields)`` method.
"""

from __future__ import annotations

from typing import Any, Mapping


class NullEventEmitter:
    """No-op emitter used when the caller does not provide one."""

    def emit(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    # Backwards-compatible alias some scripts use.
    def custom(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def child(self, _meta: Mapping[str, Any] | None = None) -> "NullEventEmitter":
        return self

    def config_emitter(self) -> "NullEventEmitter":
        return self


NULL_EVENT_EMITTER = NullEventEmitter()

__all__ = ["NULL_EVENT_EMITTER", "NullEventEmitter"]
