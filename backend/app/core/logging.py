"""Structured logging configuration for the FastAPI backend."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from .settings import AppSettings

_CORRELATION_ID: ContextVar[str | None] = ContextVar("ade_correlation_id", default=None)
_STANDARD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
}


class JSONLogFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - standard signature
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        correlation_id = getattr(record, "correlation_id", None) or _CORRELATION_ID.get()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = _coerce_value(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=_coerce_value, separators=(",", ":"))


def setup_logging(settings: AppSettings) -> None:
    """Configure the root logger with JSON output."""

    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONLogFormatter())

    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level.upper())

    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(noisy).handlers = []
        logging.getLogger(noisy).propagate = True


def bind_request_context(correlation_id: str | None) -> None:
    """Bind a correlation ID to the logging context."""

    _CORRELATION_ID.set(correlation_id)


def clear_request_context() -> None:
    """Remove the correlation ID from the logging context."""

    _CORRELATION_ID.set(None)


def _coerce_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _coerce_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_coerce_value(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # pragma: no cover - defensive fallback
            pass
    return str(value)


__all__ = [
    "JSONLogFormatter",
    "bind_request_context",
    "clear_request_context",
    "setup_logging",
]
