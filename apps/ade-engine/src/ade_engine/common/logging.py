"""Shared logging utilities for ADE runs."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO

from ade_engine.common.events import EventLogger


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_timestamp(created: float) -> str:
    """Format a LogRecord ``created`` timestamp as RFC3339-ish UTC."""
    return (
        datetime.fromtimestamp(created, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _truncate_value(value: Any, *, max_length: int = 120) -> str:
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


class JsonFormatter(logging.Formatter):
    """Formatter that renders structured log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003 - matches logging.Formatter API
        event_name = getattr(record, "event", None) or "engine.console.line"

        payload: dict[str, Any] = {
            "ts": _format_timestamp(record.created),
            "level": record.levelname.lower(),
            "event": event_name,
            "message": record.getMessage(),
        }

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
                # If formatting the traceback fails, we still want the rest of the payload.
                pass

        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Formatter that renders structured records into readable single-line text."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003 - matches logging.Formatter API
        timestamp = _format_timestamp(record.created)
        level_name = record.levelname.upper()
        event_name = getattr(record, "event", None) or "log"
        message = record.getMessage()

        if event_name == "log":
            head = f"[{timestamp}] {level_name} {record.name}: {message}"
        else:
            head = f"[{timestamp}] {level_name} {event_name}: {message}"

        extras: list[str] = []

        data = getattr(record, "data", None)
        if isinstance(data, dict) and data:
            for key in sorted(data)[:8]:
                extras.append(f"{key}={_truncate_value(data[key])}")
            if len(data) > 8:
                extras.append("…")

        if extras:
            head += " (" + ", ".join(extras) + ")"

        if record.exc_info:
            try:
                traceback_text = "".join(traceback.format_exception(*record.exc_info)).rstrip("\n")
            except Exception:
                traceback_text = ""
            if traceback_text:
                head += "\n" + traceback_text

        return head


# ---------------------------------------------------------------------------
# Run-scoped logging
# ---------------------------------------------------------------------------


@dataclass
class RunLogContext:
    """Per-run logging context with structured events."""

    logger: logging.Logger
    events: EventLogger
    _open_handles: list[IO[str]] | None = None

    def close(self) -> None:
        handles, self._open_handles = self._open_handles, None
        if not handles:
            return
        for handle in handles:
            try:
                handle.close()
            except Exception:
                # Logging must never crash the engine.
                pass

    def __enter__(self) -> "RunLogContext":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()


def start_run_logging(
    *,
    log_format: str = "text",
    enable_console_logging: bool = True,
    log_file: Path | None = None,
    log_level: int = logging.INFO,
    namespace: str = "engine",
) -> RunLogContext:
    """Start logging and event helpers for a single ADE run.

    Args:
        log_format:
            Either ``"text"`` or ``"ndjson"``.
        enable_console_logging:
            If True, emit logs to stderr.
        log_file:
            Optional file path for a per-run log file.
        log_level:
            Minimum log level for this run (defaults to INFO).
        namespace:
            Optional namespace prefix applied to emitted event names.

    Behavior:
        * Logs go to stderr when ``enable_console_logging`` is True.
        * When ``log_file`` is provided, logs are also written there.
        * ``log_format="text"`` uses TextFormatter.
        * ``log_format="ndjson"`` uses JsonFormatter.
    """
    normalized_format = (log_format or "text").strip().lower()
    if normalized_format not in {"text", "ndjson"}:
        raise ValueError("log_format must be 'text' or 'ndjson'")

    if normalized_format == "ndjson":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = TextFormatter()

    handlers: list[logging.Handler] = []
    open_handles: list[IO[str]] = []

    if enable_console_logging:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handle = log_file.open("w", encoding="utf-8", newline="\n")
        open_handles.append(file_handle)

        file_handler = logging.StreamHandler(file_handle)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    base_logger = logging.getLogger("ade_engine.run")
    base_logger.setLevel(log_level)
    base_logger.handlers = handlers
    base_logger.propagate = False

    events = EventLogger(base_logger, namespace=namespace)

    return RunLogContext(logger=base_logger, events=events, _open_handles=open_handles)


__all__ = [
    "JsonFormatter",
    "RunLogContext",
    "TextFormatter",
    "EventLogger",
    "start_run_logging",
]
