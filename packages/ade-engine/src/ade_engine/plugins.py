"""Plugin helpers for loading telemetry integrations."""

from __future__ import annotations

from importlib import import_module
from typing import Iterable

from .sinks import EventSinkFactory

__all__ = [
    "load_event_sink_factory",
    "load_event_sink_factories",
]


def _split_spec(spec: str) -> tuple[str, str]:
    module_path, separator, attr = spec.partition(":")
    if not separator:
        module_path, dot, attr = spec.rpartition(".")
        if not dot:
            raise ValueError(f"Invalid sink specification: '{spec}'")
    if not module_path or not attr:
        raise ValueError(f"Invalid sink specification: '{spec}'")
    return module_path, attr


def load_event_sink_factory(spec: str) -> EventSinkFactory:
    """Return the event sink factory referenced by ``spec``."""

    module_path, attr = _split_spec(spec)
    module = import_module(module_path)
    candidate = getattr(module, attr)
    if not callable(candidate):  # pragma: no cover - defensive guard
        raise TypeError(f"Telemetry sink factory '{spec}' is not callable")
    return candidate  # type: ignore[return-value]


def load_event_sink_factories(specs: Iterable[str]) -> tuple[EventSinkFactory, ...]:
    """Load telemetry sink factories for ``specs``."""

    factories: list[EventSinkFactory] = []
    for spec in specs:
        spec = spec.strip()
        if not spec:
            continue
        factories.append(load_event_sink_factory(spec))
    return tuple(factories)
