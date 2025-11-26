from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

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

    extras = getattr(event, "model_extra", {}) or {}
    level = extras.get("level")
    if isinstance(level, str):
        return level

    # Fall back to stderr implying warning when stream is present.
    stream = extras.get("stream")
    if stream == "stderr":
        return "warning"
    return "info"


def _context_ids(run: RunContext) -> tuple[str | None, str | None]:
    meta = run.metadata or {}
    return meta.get("workspace_id"), meta.get("configuration_id")


def _make_event(
    *,
    run: RunContext,
    type_: str,
    payload: dict[str, Any] | None = None,
    sequence: int | None = None,
    source: str | None = None,
    details: dict[str, Any] | None = None,
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
        details=details,
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
    """Unified facade for ADE events.

    This logger owns the per-run sequence counter and wraps low-level sinks so
    callers can think in terms of semantic event types (run.console, run.table.summary, ...).
    """

    run: RunContext
    event_sink: EventSink | None = None

    # Envelope metadata.
    source: str = "engine"
    emitter: str | None = None
    emitter_version: str | None = None
    correlation_id: str | None = None

    # Monotonic sequence number for this run's event stream.
    _sequence: int = field(default=0, init=False, repr=False)

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _emit(self, type_: str, *, payload: dict[str, Any] | None = None) -> None:
        if not self.event_sink:
            return

        payload = dict(payload or {})

        # Pull any event-specific details off the payload so we can merge them
        # with cross-cutting envelope details (emitter_version, correlation_id).
        event_details = payload.pop("details", None)

        base_details: dict[str, Any] = {}
        if self.emitter or self.emitter_version:
            name = self.emitter or "ade-engine"
            if self.emitter_version:
                base_details["emitter_version"] = f"{name}@{self.emitter_version}"
            else:
                base_details["emitter"] = name

        if self.correlation_id:
            base_details["correlation_id"] = self.correlation_id

        if base_details and event_details:
            merged_details: dict[str, Any] | None = {**base_details, **event_details}
        else:
            merged_details = event_details or base_details or None

        event = _make_event(
            run=self.run,
            type_=type_,
            payload=payload,
            sequence=self._next_sequence(),
            source=self.source,
            details=merged_details,
        )
        self.event_sink.emit(event)

    # --------------------------------------------------------------------- #
    # Public helpers
    # --------------------------------------------------------------------- #

    def note(self, message: str, *, level: str = "info", stream: str = "stdout", **details: Any) -> None:
        """Emit a standardized run.console event (stdout/stderr line)."""

        payload: dict[str, Any] = {"message": message, "level": level, "stream": stream}
        if details:
            payload["details"] = details
        self._emit("run.console", payload=payload)

    def event(self, type_suffix: str, *, level: str | None = "info", **payload: Any) -> None:
        """Emit a run.* lifecycle/metadata event."""

        event_payload = dict(payload)
        if level is not None:
            event_payload["level"] = level
        self._emit(f"run.{type_suffix}", payload=event_payload or None)

    def pipeline_phase(self, phase: str, **payload: Any) -> None:
        """Emit a run.phase.started event."""

        self._emit("run.phase.started", payload={"phase": phase, **payload})

    def record_table(self, table: NormalizedTable) -> None:
        """Emit a run.table.summary event for a single normalized table."""

        raw = table.mapped.raw
        validation = _aggregate_validation(table.validation_issues)

        mapped_columns = table.mapped.column_map.mapped_columns
        unmapped_columns = table.mapped.column_map.unmapped_columns

        mapped_field_names = [column.field for column in mapped_columns if column.is_satisfied]
        mapped_columns_payload = [
            {
                "field": column.field,
                "header": column.header,
                "source_column_index": column.source_column_index,
                "score": column.score,
                "is_required": column.is_required,
                "is_satisfied": column.is_satisfied,
            }
            for column in mapped_columns
        ]
        unmapped_columns_payload = [
            {
                "header": column.header,
                "source_column_index": column.source_column_index,
                "output_header": column.output_header,
            }
            for column in unmapped_columns
        ]

        column_count = len(mapped_columns) + len(unmapped_columns)

        self._emit(
            "run.table.summary",
            payload={
                "table_id": f"tbl_{raw.table_index}",
                "source_file": str(raw.source_file),
                "source_sheet": raw.source_sheet,
                "table_index": raw.table_index,
                "row_count": len(table.rows),
                "column_count": column_count,
                "mapped_fields": mapped_field_names,
                "mapped_column_count": len(mapped_columns),
                "unmapped_column_count": len(unmapped_columns),
                "validation": validation,
                "mapping": {
                    "mapped_columns": mapped_columns_payload,
                    "unmapped_columns": unmapped_columns_payload,
                },
                "details": {
                    "header_row": raw.header_row_index,
                    "first_data_row": raw.first_data_row_index,
                    "last_data_row": raw.last_data_row_index,
                },
            },
        )

    def validation_issue(self, **payload: Any) -> None:
        """Emit a fine-grained run.validation.issue event."""

        self._emit("run.validation.issue", payload=payload)

    def validation_summary(self, issues: Iterable[Any]) -> None:
        """Emit a run.validation.summary event across all tables in the run."""

        issues_list = list(issues)
        if not issues_list:
            return

        summary = _aggregate_validation(issues_list)
        self._emit("run.validation.summary", payload=summary)


def _aggregate_validation(issues: list[Any]) -> dict[str, Any]:
    """Aggregate validation issues into a compact summary.

    Returned shape aligns with the examples used for ``run.table.summary`` and
    ``run.validation.summary`` events:

    {
        "issues_total": 5,
        "issues_by_severity": {...},
        "issues_by_code": {...},
        "issues_by_field": {...},
        "max_severity": "warning"
    }
    """

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
        "issues_total": total,
        "issues_by_severity": dict(by_severity),
        "issues_by_code": dict(by_code),
        "issues_by_field": summary_by_field,
        "max_severity": max_severity,
    }
