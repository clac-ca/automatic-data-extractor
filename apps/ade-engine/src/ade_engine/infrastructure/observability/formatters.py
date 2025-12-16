from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from ade_engine.models.events import DEFAULT_EVENT, ENGINE_NAMESPACE


def _rfc3339_utc(created: float) -> str:
    return (
        datetime.fromtimestamp(created, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _truncate(value: Any, *, max_len: int = 120) -> str:
    text = str(value)
    return text if len(text) <= max_len else (text[: max_len - 1] + "…")


class _StructuredFormatter(logging.Formatter):
    def _to_event_record(self, record: logging.LogRecord) -> dict[str, Any]:
        # These are injected by RunLogger.process; fallbacks keep formatters safe.
        event_id = getattr(record, "event_id", None) or uuid.uuid4().hex
        engine_run_id = getattr(record, "engine_run_id", None) or ""
        event = getattr(record, "event", None) or DEFAULT_EVENT
        data = getattr(record, "data", None)

        out: dict[str, Any] = {
            "event_id": str(event_id),
            "engine_run_id": str(engine_run_id),
            "timestamp": _rfc3339_utc(record.created),
            "level": record.levelname.lower(),
            "event": str(event),
            "message": record.getMessage(),
        }

        if isinstance(data, Mapping) and data:
            out["data"] = dict(data)

        if record.exc_info:
            exc_type, exc, _tb = record.exc_info
            out["error"] = {
                "type": getattr(exc_type, "__name__", str(exc_type)),
                "message": "" if exc is None else str(exc),
                "stack_trace": self.formatException(record.exc_info),
            }

        return out


class NdjsonFormatter(_StructuredFormatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload = self._to_event_record(record)
        try:
            return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
        except Exception as e:  # pragma: no cover
            fallback = {
                "event_id": payload.get("event_id") or uuid.uuid4().hex,
                "engine_run_id": payload.get("engine_run_id") or "",
                "timestamp": _rfc3339_utc(record.created),
                "level": "error",
                "event": f"{ENGINE_NAMESPACE}.logging.serialization_failed",
                "message": f"Failed to serialize log record: {e}",
            }
            return json.dumps(fallback, ensure_ascii=False, default=str, separators=(",", ":"))


class TextFormatter(_StructuredFormatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload = self._to_event_record(record)
        ts = payload["timestamp"]
        lvl = payload["level"].upper()
        event = payload.get("event") or ""
        msg = payload["message"]

        head = f"[{ts}] {lvl} {event}"
        if msg and msg != event:
            head += f": {msg}"

        data = payload.get("data")
        if isinstance(data, Mapping) and data:
            items: list[str] = []
            for key in sorted(data, key=str)[:8]:
                items.append(f"{key}={_truncate(data[key])}")
            if len(data) > 8:
                items.append("…")
            head += " (" + ", ".join(items) + ")"

        err = payload.get("error")
        if isinstance(err, Mapping):
            stack = err.get("stack_trace")
            if stack:
                head += "\n" + str(stack).rstrip("\n")

        return head


__all__ = [
    "NdjsonFormatter",
    "TextFormatter",
]

