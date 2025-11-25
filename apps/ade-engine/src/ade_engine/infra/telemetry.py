from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from ade_engine.infra.artifact import ArtifactSink
from ade_engine.core.types import NormalizedTable, RunContext
from ade_engine.schemas.telemetry import TelemetryEnvelope, TelemetryEvent


_LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EventSink(Protocol):
    """Protocol for telemetry event emission."""

    def log(self, event: str, *, run: RunContext, level: str = "info", **payload: Any) -> None: ...


@dataclass
class FileEventSink:
    """Append-only NDJSON writer for telemetry events."""

    path: Path
    min_level: str = "info"

    def _should_log(self, level: str) -> bool:
        level_key = level.lower()
        return _LEVEL_ORDER.get(level_key, 0) >= _LEVEL_ORDER.get(self.min_level, 0)

    def log(self, event: str, *, run: RunContext, level: str = "info", **payload: Any) -> None:
        if not self._should_log(level):
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        envelope = TelemetryEnvelope(
            run_id=run.run_id,
            timestamp=_timestamp(),
            metadata=dict(run.metadata) if run.metadata else {},
            event=TelemetryEvent(event=event, level=level, payload=payload),
        )
        line = json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


@dataclass
class DispatchEventSink:
    """Fan out events to multiple sinks."""

    sinks: Iterable[EventSink]

    def log(self, event: str, *, run: RunContext, level: str = "info", **payload: Any) -> None:
        for sink in self.sinks:
            sink.log(event, run=run, level=level, **payload)


@dataclass
class TelemetryConfig:
    """Engine-level telemetry configuration."""

    correlation_id: str | None = None
    min_event_level: str = "info"
    event_sink_factories: list[Callable[[RunContext], EventSink]] = field(default_factory=list)

    def build_sink(self, run: RunContext) -> EventSink:
        sinks = [factory(run) for factory in self.event_sink_factories]
        sinks.append(FileEventSink(path=run.paths.events_path, min_level=self.min_event_level))
        return DispatchEventSink(sinks)


@dataclass
class PipelineLogger:
    """Unified facade for artifact notes and telemetry events."""

    run: RunContext
    artifact_sink: ArtifactSink
    event_sink: EventSink | None = None

    def note(self, message: str, *, level: str = "info", **details: Any) -> None:
        self.artifact_sink.note(message, level=level, details=details or None)
        if self.event_sink:
            self.event_sink.log("note", run=self.run, level=level, message=message, **details)

    def event(self, name: str, *, level: str = "info", **payload: Any) -> None:
        if self.event_sink:
            self.event_sink.log(name, run=self.run, level=level, **payload)

    def transition(self, phase: str, **payload: Any) -> None:
        self.event("pipeline_transition", level="info", phase=phase, **payload)

    def record_table(self, table: NormalizedTable) -> None:
        self.artifact_sink.record_table(table)
        if self.event_sink:
            raw = table.mapped.raw
            self.event_sink.log(
                "table_completed",
                run=self.run,
                level="info",
                source_file=str(raw.source_file),
                source_sheet=raw.source_sheet,
                table_index=raw.table_index,
                validation_issue_count=len(table.validation_issues),
            )
