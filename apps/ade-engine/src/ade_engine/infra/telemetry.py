from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from ade_engine.infra.artifact import ArtifactSink
from ade_engine.core.types import NormalizedTable, RunContext
from ade_engine.schemas.telemetry import AdeEvent

_LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_level(event: AdeEvent) -> str:
    """Best-effort level extraction for filtering."""

    if event.run and "level" in event.run:
        return str(event.run.get("level"))
    if event.log and "level" in event.log:
        return str(event.log.get("level"))
    return "info"


def _context_ids(run: RunContext) -> tuple[str | None, str | None]:
    meta = run.metadata or {}
    return meta.get("workspace_id"), meta.get("configuration_id")


def _make_event(
    *,
    run: RunContext,
    type_: str,
    run_payload: dict[str, Any] | None = None,
    build_payload: dict[str, Any] | None = None,
    env_payload: dict[str, Any] | None = None,
    validation_payload: dict[str, Any] | None = None,
    execution_payload: dict[str, Any] | None = None,
    output_delta: dict[str, Any] | None = None,
    log_payload: dict[str, Any] | None = None,
    error_payload: dict[str, Any] | None = None,
) -> AdeEvent:
    workspace_id, configuration_id = _context_ids(run)
    return AdeEvent(
        type=type_,
        created_at=_now(),
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        run_id=run.run_id,
        run=run_payload,
        build=build_payload,
        env=env_payload,
        validation=validation_payload,
        execution=execution_payload,
        output_delta=output_delta,
        log=log_payload,
        error=error_payload,
    )


class EventSink(Protocol):
    """Protocol for ADE event emission."""

    def emit(self, event: AdeEvent) -> None: ...


@dataclass
class FileEventSink:
    """Append-only NDJSON writer for ADE events."""

    path: Path
    min_level: str = "info"

    def emit(self, event: AdeEvent) -> None:
        level = _event_level(event)
        level_key = level.lower()
        if _LEVEL_ORDER.get(level_key, 0) < _LEVEL_ORDER.get(self.min_level, 0):
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


@dataclass
class DispatchEventSink:
    """Fan out events to multiple sinks."""

    sinks: Iterable[EventSink]

    def emit(self, event: AdeEvent) -> None:
        for sink in self.sinks:
            sink.emit(event)


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
    """Unified facade for artifact notes and ADE events."""

    run: RunContext
    artifact_sink: ArtifactSink
    event_sink: EventSink | None = None

    def _emit(
        self,
        type_suffix: str,
        *,
        run_payload: dict[str, Any] | None = None,
        build_payload: dict[str, Any] | None = None,
        env_payload: dict[str, Any] | None = None,
        validation_payload: dict[str, Any] | None = None,
        execution_payload: dict[str, Any] | None = None,
        output_delta: dict[str, Any] | None = None,
        log_payload: dict[str, Any] | None = None,
        error_payload: dict[str, Any] | None = None,
    ) -> None:
        if not self.event_sink:
            return

        event = _make_event(
            run=self.run,
            type_=f"run.{type_suffix}",
            run_payload=run_payload,
            build_payload=build_payload,
            env_payload=env_payload,
            validation_payload=validation_payload,
            execution_payload=execution_payload,
            output_delta=output_delta,
            log_payload=log_payload,
            error_payload=error_payload,
        )
        self.event_sink.emit(event)

    def note(self, message: str, *, level: str = "info", **details: Any) -> None:
        self.artifact_sink.note(message, level=level, details=details or None)
        run_payload = {"message": message, "level": level}
        if details:
            run_payload["details"] = details
        self._emit("note", run_payload=run_payload)

    def event(self, type_suffix: str, *, level: str | None = "info", **payload: Any) -> None:
        run_payload = dict(payload)
        if level is not None:
            run_payload["level"] = level
        self._emit(type_suffix, run_payload=run_payload or None)

    def pipeline_phase(self, phase: str, **payload: Any) -> None:
        self._emit("pipeline.progress", run_payload={"phase": phase, **payload})

    def record_table(self, table: NormalizedTable) -> None:
        self.artifact_sink.record_table(table)
        raw = table.mapped.raw
        self._emit(
            "table.summary",
            output_delta={
                "kind": "table_summary",
                "table": {
                    "source_file": str(raw.source_file),
                    "source_sheet": raw.source_sheet,
                    "table_index": raw.table_index,
                    "row_count": len(table.rows),
                    "validation_issue_counts": {
                        "error": len([i for i in table.validation_issues if i.severity == "error"]),
                        "warning": len([i for i in table.validation_issues if i.severity == "warning"]),
                    },
                },
            },
        )

    def validation_issue(self, **payload: Any) -> None:
        self._emit("validation.issue.delta", validation_payload=payload)
