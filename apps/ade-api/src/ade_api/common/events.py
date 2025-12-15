from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

EventRecord = dict[str, Any]


def utc_rfc3339_now() -> str:
    """Render a UTC timestamp in RFC3339 format."""

    return datetime.now(tz=UTC).isoformat()


def new_event_record(
    *,
    event: str,
    message: str | None = None,
    level: str = "info",
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    event_id: str | None = None,
    engine_run_id: str | None = None,
    timestamp: str | None = None,
) -> EventRecord:
    """Create a new EventRecord matching the engine envelope."""

    record: EventRecord = {
        "event_id": event_id or uuid4().hex,
        "engine_run_id": engine_run_id or "",
        "timestamp": timestamp or utc_rfc3339_now(),
        "level": level,
        "event": event,
        "message": message or "",
        "data": data or {},
    }
    if error is not None:
        record["error"] = error
    return record


def coerce_event_record(obj: Any) -> EventRecord | None:
    """Best-effort conversion of raw JSON payloads into EventRecords."""

    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    if "event" not in obj:
        return None
    # Preserve the original mapping but ensure required fields exist.
    record: EventRecord = dict(obj)
    record.setdefault("event_id", uuid4().hex)
    record.setdefault("engine_run_id", "")
    record.setdefault("timestamp", utc_rfc3339_now())
    record.setdefault("level", "info")
    record.setdefault("message", "")
    record.setdefault("data", {})
    return record


def ensure_event_context(
    event: EventRecord,
    *,
    job_id: str | None = None,
    workspace_id: str | None = None,
    build_id: str | None = None,
    configuration_id: str | None = None,
) -> EventRecord:
    """Attach API context into the EventRecord data payload."""

    data = dict(event.get("data") or {})
    if job_id is not None:
        data.setdefault("jobId", job_id)
    if workspace_id is not None:
        data.setdefault("workspaceId", workspace_id)
    if build_id is not None:
        data.setdefault("buildId", build_id)
    if configuration_id is not None:
        data.setdefault("configurationId", configuration_id)

    enriched = dict(event)
    enriched["data"] = data
    return enriched


@dataclass(slots=True)
class EventRecordLog:
    """Utility to read EventRecords from NDJSON files."""

    path: str
    _events: list[EventRecord] = field(default_factory=list)

    def iter(self, *, after_sequence: int | None = None) -> Iterable[EventRecord]:
        try:
            with open(self.path, encoding="utf-8") as handle:
                cursor = 0
                skip = after_sequence or 0
                for raw in handle:
                    if not raw.strip():
                        continue
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(parsed, dict):
                        continue
                    cursor += 1
                    if cursor <= skip:
                        continue
                    if not isinstance(parsed.get("sequence"), int):
                        parsed["sequence"] = cursor
                    yield parsed
        except FileNotFoundError:
            return

    def last_cursor(self) -> int:
        cursor = 0
        for _ in self.iter():
            cursor += 1
        return cursor
