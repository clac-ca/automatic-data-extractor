from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol
from uuid import UUID

from ade_engine.core.types import NormalizedTable, RunContext
from ade_engine.schemas.telemetry import AdeEvent

# Treat "success" as an info-level event for filtering.
_LEVEL_ORDER = {
    "debug": 0,
    "info": 1,
    "success": 1,
    "warning": 2,
    "error": 3,
    "critical": 4,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_level(event: AdeEvent) -> str:
    """Best-effort level extraction for filtering."""

    payload = event.payload_dict()
    level = payload.get("level")
    if isinstance(level, str):
        return level

    # Fall back to stderr implying warning when stream is present.
    stream = payload.get("stream")
    if stream == "stderr":
        return "warning"
    return "info"


def _coerce_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except Exception:
        return None


def _context_ids(run: RunContext) -> tuple[UUID | None, UUID | None]:
    meta = run.metadata or {}
    return _coerce_uuid(meta.get("workspace_id")), _coerce_uuid(meta.get("configuration_id"))


def _make_event(
    *,
    run: RunContext,
    type_: str,
    payload: dict[str, Any] | None = None,
    sequence: int | None = None,
    source: str | None = None,
) -> AdeEvent:
    """Construct a typed AdeEvent with the common envelope fields populated."""

    workspace_id, configuration_id = _context_ids(run)
    payload = payload or {}

    return AdeEvent(
        type=type_,
        created_at=_now(),
        sequence=sequence,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        run_id=run.run_id,
        source=source,
        payload=payload,
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
        line = json.dumps(event.model_dump(mode="json", by_alias=True), ensure_ascii=False)
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


def _aggregate_validation(issues: list[Any]) -> dict[str, Any]:
    """Aggregate validation issues into a compact summary."""

    total = 0
    by_severity: defaultdict[str, int] = defaultdict(int)
    by_code: defaultdict[str, int] = defaultdict(int)
    by_field: dict[str, dict[str, Any]] = {}

    max_severity_rank = -1
    max_severity: str | None = None
    severity_order = ["info", "warning", "error", "critical"]

    for issue in issues:
        severity = str(getattr(issue, "severity", "") or "")
        code = str(getattr(issue, "code", "") or "")
        field = str(getattr(issue, "field", "") or "")

        total += 1

        if severity:
            by_severity[severity] += 1
            if severity in severity_order:
                rank = severity_order.index(severity)
                if rank > max_severity_rank:
                    max_severity_rank = rank
                    max_severity = severity

        if code:
            by_code[code] += 1

        if field:
            bucket = by_field.setdefault(
                field,
                {
                    "issues_total": 0,
                    "issues_by_severity": defaultdict(int),
                    "issues_by_code": defaultdict(int),
                },
            )
            bucket["issues_total"] += 1
            if severity:
                bucket["issues_by_severity"][severity] += 1
            if code:
                bucket["issues_by_code"][code] += 1

    summary_by_field = {
        field: {
            "issues_total": data["issues_total"],
            "issues_by_severity": dict(data["issues_by_severity"]),
            "issues_by_code": dict(data["issues_by_code"]),
        }
        for field, data in by_field.items()
    }

    return {
        "total": total,
        "issues_total": total,
        "issues_by_severity": dict(by_severity),
        "issues_by_code": dict(by_code),
        "issues_by_field": summary_by_field,
        "max_severity": max_severity,
    }


__all__ = [
    "DispatchEventSink",
    "EventSink",
    "FileEventSink",
    "TelemetryConfig",
    "_aggregate_validation",
    "_context_ids",
    "_make_event",
    "_now",
    "_coerce_uuid",
]
