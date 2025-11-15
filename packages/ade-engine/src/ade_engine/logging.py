"""Structured logging helpers that sit on top of artifact/event sinks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .model import JobContext
from .sinks import ArtifactSink, EventSink
from .telemetry import TelemetryBindings, level_value


@dataclass(slots=True)
class StructuredLogger:
    """Bridge artifact and event sinks with a consistent API."""

    job: JobContext
    telemetry: TelemetryBindings
    runtime_logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("ade_engine.pipeline")
    )
    artifact: ArtifactSink = field(init=False)
    events: EventSink = field(init=False)

    def __post_init__(self) -> None:
        self.artifact = self.telemetry.artifact
        self.events = self.telemetry.events

    def note(self, message: str, *, level: str = "info", **details: Any) -> None:
        """Record a structured note in the artifact output."""

        record_level = level_value(level)
        if self.telemetry.enabled_for_note(level):
            enriched = self.telemetry.decorate_details(details)
            self.artifact.note(message, level=level, **enriched)
        self.runtime_logger.log(record_level, message, extra={"details": details})

    def event(self, name: str, *, level: str = "info", **payload: Any) -> None:
        """Emit a structured event for downstream consumers."""

        record_level = level_value(level)
        enriched = {"level": level, **payload}
        enriched = self.telemetry.decorate_payload(enriched)
        if self.telemetry.enabled_for_event(level):
            self.events.log(name, job=self.job, **enriched)
        self.runtime_logger.log(
            record_level,
            "event %s",
            name,
            extra={"payload": enriched},
        )

    def record_table(self, table: dict[str, Any]) -> None:
        """Persist table metadata to the artifact."""

        self.artifact.record_table(table)

    def flush(self) -> None:
        """Flush the artifact sink to disk."""

        self.artifact.flush()

    def transition(self, phase: str, **payload: Any) -> None:
        """Announce a pipeline phase transition."""

        event_payload = {"phase": phase, **payload}
        self.event("pipeline_transition", level="debug", **event_payload)
        self.note(
            f"Pipeline entered '{phase}' phase",
            level="debug",
            phase=phase,
            **payload,
        )


__all__ = ["StructuredLogger"]
