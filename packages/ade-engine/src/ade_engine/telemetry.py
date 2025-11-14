"""Telemetry configuration helpers for ADE runtime instrumentation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .model import JobContext, JobPaths
from .sinks import ArtifactSink, EventSink, FileSinkProvider, SinkProvider

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
        events = selected.events(job)
        return TelemetryBindings(
            job=job,
            config=self,
            provider=selected,
            artifact=artifact,
            events=events,
        )


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

