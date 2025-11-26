from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol
from collections import defaultdict

from ade_engine.core.types import NormalizedTable, RunContext
from ade_engine.schemas.telemetry import AdeEvent

_LEVEL_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_level(event: AdeEvent) -> str:
    """Best-effort level extraction for filtering."""

    extras = getattr(event, "model_extra", {}) or {}
    level = extras.get("level")
    if isinstance(level, str):
        return level
    # Fall back to stderr implying warning when stream is present
    stream = extras.get("stream")
    if stream == "stderr":
        return "warning"
    return "info"


def _context_ids(run: RunContext) -> tuple[str | None, str | None]:
    meta = run.metadata or {}
    return meta.get("workspace_id"), meta.get("configuration_id")


def _make_event(*, run: RunContext, type_: str, payload: dict[str, Any] | None = None) -> AdeEvent:
    workspace_id, configuration_id = _context_ids(run)
    payload = payload or {}
    return AdeEvent(
        type=type_,
        created_at=_now(),
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        run_id=run.run_id,
        **payload,
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
        sinks.append(FileEventSink(path=run.paths.logs_dir / "events.ndjson", min_level=self.min_event_level))
        return DispatchEventSink(sinks)


@dataclass
class PipelineLogger:
    """Unified facade for ADE events."""

    run: RunContext
    event_sink: EventSink | None = None

    def _emit(self, type_: str, *, payload: dict[str, Any] | None = None) -> None:
        if not self.event_sink:
            return

        event = _make_event(run=self.run, type_=type_, payload=payload or {})
        self.event_sink.emit(event)

    def note(self, message: str, *, level: str = "info", stream: str = "stdout", **details: Any) -> None:
        payload: dict[str, Any] = {"message": message, "level": level, "stream": stream}
        if details:
            payload["details"] = details
        self._emit("run.console", payload=payload)

    def event(self, type_suffix: str, *, level: str | None = "info", **payload: Any) -> None:
        event_payload = dict(payload)
        if level is not None:
            event_payload["level"] = level
        self._emit(f"run.{type_suffix}", payload=event_payload or None)

    def pipeline_phase(self, phase: str, **payload: Any) -> None:
        self._emit("run.phase.started", payload={"phase": phase, **payload})

    def record_table(self, table: NormalizedTable) -> None:
        raw = table.mapped.raw
        validation = _aggregate_validation(table.validation_issues)
        mapped_fields = [
            {
                "field": column.field,
                "score": column.score,
                "is_required": column.is_required,
                "is_satisfied": column.is_satisfied,
                "header": column.header,
                "source_column_index": column.source_column_index,
            }
            for column in table.mapped.column_map.mapped_columns
        ]
        unmapped_columns = [
            {
                "header": column.header,
                "source_column_index": column.source_column_index,
                "output_header": column.output_header,
            }
            for column in table.mapped.column_map.unmapped_columns
        ]
        column_count = len(table.mapped.column_map.mapped_columns) + len(table.mapped.column_map.unmapped_columns)
        self._emit(
            "run.table.summary",
            payload={
                "table_id": f"tbl_{raw.table_index}",
                "source_file": str(raw.source_file),
                "source_sheet": raw.source_sheet,
                "table_index": raw.table_index,
                "row_count": len(table.rows),
                "column_count": column_count,
                "mapped_fields": mapped_fields,
                "unmapped_column_count": len(table.mapped.column_map.unmapped_columns),
                "unmapped_columns": unmapped_columns,
                "validation": validation,
                "details": {
                    "header_row": raw.header_row_index,
                    "first_data_row": raw.first_data_row_index,
                    "last_data_row": raw.last_data_row_index,
                },
            },
        )

    def validation_issue(self, **payload: Any) -> None:
        self._emit("run.validation.issue", payload=payload)


def _aggregate_validation(issues: list[Any]) -> dict[str, Any]:
    total = 0
    by_severity: defaultdict[str, int] = defaultdict(int)
    by_code: defaultdict[str, int] = defaultdict(int)
    by_field: dict[str, dict[str, Any]] = {}

    for issue in issues:
        severity = str(getattr(issue, "severity", None) or "")
        code = str(getattr(issue, "code", None) or "")
        field = str(getattr(issue, "field", None) or "")

        total += 1
        if severity:
            by_severity[severity] += 1
        if code:
            by_code[code] += 1

        bucket = by_field.setdefault(
            field,
            {
                "total": 0,
                "by_severity": defaultdict(int),
                "by_code": defaultdict(int),
            },
        )
        bucket["total"] += 1
        if severity:
            bucket["by_severity"][severity] += 1
        if code:
            bucket["by_code"][code] += 1

    return {
        "total": total,
        "by_severity": dict(by_severity),
        "by_code": dict(by_code),
        "by_field": {
            field: {
                "total": data["total"],
                "by_severity": dict(data["by_severity"]),
                "by_code": dict(data["by_code"]),
            }
            for field, data in by_field.items()
        },
    }
