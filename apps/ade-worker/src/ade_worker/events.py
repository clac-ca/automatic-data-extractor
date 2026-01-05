"""Event helpers for worker-generated NDJSON logs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

EventRecord = dict[str, Any]


def utc_rfc3339_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def new_event_record(
    *,
    event: str,
    message: str | None = None,
    level: str = "info",
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> EventRecord:
    record: EventRecord = {
        "event_id": event_id or uuid4().hex,
        "engine_run_id": "",
        "timestamp": timestamp or utc_rfc3339_now(),
        "level": level,
        "event": event,
        "message": message or "",
        "data": data or {},
    }
    if error is not None:
        record["error"] = error
    return record


def coerce_event_record(raw: str) -> EventRecord | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or "event" not in parsed:
        return None
    record: EventRecord = dict(parsed)
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
    data = dict(event.get("data") or {})
    if job_id:
        data.setdefault("jobId", job_id)
    if workspace_id:
        data.setdefault("workspaceId", workspace_id)
    if build_id:
        data.setdefault("buildId", build_id)
    if configuration_id:
        data.setdefault("configurationId", configuration_id)
    enriched = dict(event)
    enriched["data"] = data
    return enriched


__all__ = ["EventRecord", "new_event_record", "coerce_event_record", "ensure_event_context"]
