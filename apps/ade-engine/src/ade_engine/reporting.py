"""Reporting utilities: structured logging + domain events.

Design goals:
- One logger per run, configured once.
- One handler per run.
  - ``text`` mode renders human-friendly lines.
  - ``ndjson`` mode renders one JSON object per line (NDJSON).
- Domain events are just log records with an ``event`` name and optional structured ``data``.
- Engine code and config scripts use the standard ``logger`` *and* a tiny helper:
  ``event_emitter.emit("event.name", **data)``.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO, Mapping


def _format_ts(created: float) -> str:
    """Format a LogRecord ``created`` timestamp as RFC3339-ish UTC."""
    return (
        datetime.fromtimestamp(created, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _short(value: Any, *, limit: int = 120) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class RunLogger(logging.LoggerAdapter):
    """LoggerAdapter that injects ``run_id`` and ``meta`` into every record."""

    def __init__(self, logger: logging.Logger, *, run_id: str, meta: Mapping[str, Any] | None = None) -> None:
        super().__init__(logger, {"run_id": str(run_id), "meta": dict(meta or {})})

    def process(self, msg: Any, kwargs: dict[str, Any]):
        extra = dict(kwargs.pop("extra", {}) or {})
        extra.setdefault("run_id", self.extra.get("run_id"))
        meta = self.extra.get("meta") or {}
        if meta:
            # Avoid surprising mutation by downstream code.
            extra.setdefault("meta", dict(meta))
        kwargs["extra"] = extra
        return msg, kwargs


class EventEmitter:
    """Tiny helper to emit domain events without touching ``extra``."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def emit(
        self,
        event: str,
        *,
        message: str | None = None,
        level: int = logging.INFO,
        stage: str | None = None,
        **data: Any,
    ) -> None:
        """Emit a domain event as a structured log record.

        Args:
          event: Stable event name (e.g. ``table.mapped``).
          message: Optional human-friendly message (defaults to the event name).
          level: Standard logging level (INFO by default).
          stage: Optional engine stage (top-level field).
          **data: Structured payload, stored under ``data`` in NDJSON output.
        """
        extra: dict[str, Any] = {"event": str(event)}
        if stage is not None:
            extra["stage"] = str(stage)
        if data:
            extra["data"] = data
        self._logger.log(level, message or str(event), extra=extra)


class JsonFormatter(logging.Formatter):
    """Formatter that renders structured log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003 - matches logging.Formatter API
        event = getattr(record, "event", None) or "log"

        payload: dict[str, Any] = {
            "ts": _format_ts(record.created),
            "level": record.levelname.lower(),
            "event": event,
            "message": record.getMessage(),
        }

        run_id = getattr(record, "run_id", None)
        if run_id:
            payload["run_id"] = run_id

        meta = getattr(record, "meta", None)
        if meta:
            payload["meta"] = meta

        stage = getattr(record, "stage", None)
        if stage:
            payload["stage"] = stage

        data = getattr(record, "data", None)
        if data is not None:
            payload["data"] = data

        if record.exc_info:
            exc_type, exc, _ = record.exc_info
            payload["exc_type"] = getattr(exc_type, "__name__", None)
            payload["exc"] = str(exc)
            try:
                payload["traceback"] = "".join(traceback.format_exception(*record.exc_info))
            except Exception:
                pass

        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Formatter that renders structured records into readable single-line text."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003 - matches logging.Formatter API
        ts = _format_ts(record.created)
        level = record.levelname.upper()
        event = getattr(record, "event", None) or "log"
        message = record.getMessage()

        if event == "log":
            head = f"[{ts}] {level} {record.name}: {message}"
        else:
            head = f"[{ts}] {level} {event}: {message}"

        extras: list[str] = []
        stage = getattr(record, "stage", None)
        if stage:
            extras.append(f"stage={stage}")

        data = getattr(record, "data", None)
        if isinstance(data, dict) and data:
            # Show a small, stable slice of data fields.
            for key in sorted(data)[:8]:
                extras.append(f"{key}={_short(data[key])}")
            if len(data) > 8:
                extras.append("…")

        if extras:
            head += " (" + ", ".join(extras) + ")"

        if record.exc_info:
            try:
                tb = "".join(traceback.format_exception(*record.exc_info)).rstrip("\n")
            except Exception:
                tb = ""
            if tb:
                head += "\n" + tb

        return head


@dataclass
class Reporter:
    """Bundle of run-scoped logger and event helper."""

    logger: RunLogger
    event_emitter: EventEmitter
    _handle: IO[str] | None = None

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            handle.close()
        except Exception:
            pass

    def __enter__(self) -> "Reporter":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()


def build_reporting(
    fmt: str,
    *,
    run_id: str,
    meta: Mapping[str, Any] | None = None,
    file_path: Path | None = None,
    level: int = logging.INFO,
) -> Reporter:
    """Create the per-run logger and event helper.

    - If ``file_path`` is provided, output goes there.
    - Otherwise: ``text`` -> stderr, ``ndjson`` -> stdout.
    """
    fmt_value = str(fmt or "text").strip().lower()
    if fmt_value not in {"text", "ndjson"}:
        raise ValueError("fmt must be 'text' or 'ndjson'")

    handle: IO[str] | None = None
    if file_path is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        handle = file_path.open("w", encoding="utf-8", newline="\n")
        stream: IO[str] = handle
    else:
        stream = sys.stdout if fmt_value == "ndjson" else sys.stderr

    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter() if fmt_value == "ndjson" else TextFormatter())

    base_logger = logging.getLogger(f"ade_engine.run.{run_id}")
    base_logger.setLevel(level)
    base_logger.handlers.clear()
    base_logger.propagate = False
    base_logger.addHandler(handler)

    run_logger = RunLogger(base_logger, run_id=run_id, meta=meta)
    event_emitter = EventEmitter(run_logger)

    return Reporter(logger=run_logger, event_emitter=event_emitter, _handle=handle)


@contextmanager
def protect_stdout(*, enabled: bool = True):
    """Redirect stdout to stderr to keep NDJSON output clean."""
    if not enabled:
        yield
        return
    with redirect_stdout(sys.stderr):
        yield


__all__ = [
    "EventEmitter",
    "Reporter",
    "RunLogger",
    "build_reporting",
    "protect_stdout",
]
