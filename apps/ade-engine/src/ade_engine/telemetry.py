"""Telemetry configuration helpers for ADE runtime instrumentation."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from .model import JobContext, JobPaths
from .plugins import load_event_sink_factories
from .sinks import (
    ArtifactSink,
    DispatchEventSink,
    EventSink,
    EventSinkFactory,
    FileSinkProvider,
    SinkProvider,
)

_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def _normalize_level(level: str) -> str:
    return (level or "info").lower()


def level_value(level: str) -> int:
    """Return the logging level numeric value for ``level``."""

    return _LEVELS.get(_normalize_level(level), logging.INFO)


@dataclass(slots=True)
class TelemetryConfig:
    """Standardize runtime telemetry behavior across sinks."""

    correlation_id: str | None = None
    min_note_level: str = "debug"
    min_event_level: str = "debug"
    sink_provider: SinkProvider | None = None
    event_sink_factories: tuple[EventSinkFactory, ...] = field(default_factory=tuple)
    event_sink_specs: tuple[str, ...] = field(default_factory=tuple)
    sink_spec_env: str | None = "ADE_TELEMETRY_SINKS"

    def bind(
        self,
        job: JobContext,
        paths: JobPaths,
        *,
        provider: SinkProvider | None = None,
    ) -> TelemetryBindings:
        """Create sink bindings for ``job`` using configured defaults."""

        selected = provider or self.sink_provider or FileSinkProvider(paths)
        artifact = selected.artifact(job)
        base_events = selected.events(job)
        extra_sinks = [factory(job, paths) for factory in self._resolve_event_factories()]
        events: EventSink
        if extra_sinks:
            events = DispatchEventSink((base_events, *extra_sinks))
        else:
            events = base_events
        return TelemetryBindings(
            job=job,
            config=self,
            provider=selected,
            artifact=artifact,
            events=events,
        )

    def _resolve_event_factories(self) -> tuple[EventSinkFactory, ...]:
        """Return configured event sink factories including env overrides."""

        factories = list(self.event_sink_factories)
        specs: list[str] = list(self.event_sink_specs)
        if self.sink_spec_env:
            raw_value = os.getenv(self.sink_spec_env, "")
            specs.extend(part.strip() for part in raw_value.split(",") if part.strip())
        if specs:
            factories.extend(load_event_sink_factories(specs))
        return tuple(factories)


@dataclass(slots=True)
class TelemetryBindings:
    """Concrete sink bindings produced from a :class:`TelemetryConfig`."""

    job: JobContext
    config: TelemetryConfig
    provider: SinkProvider
    artifact: ArtifactSink
    events: EventSink

    def enabled_for_note(self, level: str) -> bool:
        """Return ``True`` when ``level`` meets the note severity threshold."""

        threshold = level_value(self.config.min_note_level)
        return level_value(level) >= threshold

    def enabled_for_event(self, level: str) -> bool:
        """Return ``True`` when ``level`` meets the event severity threshold."""

        threshold = level_value(self.config.min_event_level)
        return level_value(level) >= threshold

    def decorate_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Attach correlation metadata to artifact note details."""

        if not self.config.correlation_id:
            return details
        enriched = dict(details)
        enriched.setdefault("correlation_id", self.config.correlation_id)
        return enriched

    def decorate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Attach correlation metadata to event payloads."""

        if not self.config.correlation_id:
            return payload
        enriched = dict(payload)
        enriched.setdefault("correlation_id", self.config.correlation_id)
        return enriched


__all__ = [
    "TelemetryBindings",
    "TelemetryConfig",
    "level_value",
]

