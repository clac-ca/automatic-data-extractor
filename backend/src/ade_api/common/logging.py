"""Logging configuration and helpers for the ADE API backend.

This module configures process-wide logging and supports two formats:

* human-readable console logs, and
* structured JSON logs for production ingestion.

It also exposes helpers for:

* binding a request-scoped correlation ID, and
* building consistent `extra` payloads for structured logs.

Everything uses the standard :mod:`logging` library.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ade_api.settings import Settings

# ---------------------------------------------------------------------------
# Context and constants
# ---------------------------------------------------------------------------

# Request-scoped correlation ID, set/cleared by RequestContextMiddleware.
_CORRELATION_ID: ContextVar[str | None] = ContextVar(
    "api_app_correlation_id",
    default=None,
)

# Attributes that are already handled by logging and should not be copied into
# the extra key=value list.
_STANDARD_ATTRS: set[str] = {
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
    # We handle this explicitly in the base format.
    "correlation_id",
    # Uvicorn / asyncio add these; usually not useful in app logs.
    "taskName",
    "color_message",
}

_CONFIGURED_FLAG = "_ade_configured"


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


class ConsoleLogFormatter(logging.Formatter):
    """Render log records as single-line console output.

    Example line:

        2025-11-27T02:57:00.302Z INFO  ade_api.main [cid=1234abcd] ade_api.startup
        safe_mode=False auth_disabled=True
    """

    # ISO8601-ish UTC timestamp (seconds) – we'll append millis and 'Z'.
    _time_format = "%Y-%m-%dT%H:%M:%S"

    def __init__(self) -> None:
        # correlation_id will be injected into the record in format().
        fmt = "%(asctime)s %(levelname)-5s %(name)s [cid=%(correlation_id)s] %(message)s"
        super().__init__(fmt=fmt, datefmt=self._time_format)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        pattern = datefmt or self._time_format
        base = dt.strftime(pattern)
        # Attach milliseconds + Z suffix.
        return f"{base}.{int(record.msecs):03d}Z"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - std signature
        # Ensure correlation_id is always present so the format string works.
        cid = getattr(record, "correlation_id", None) or _CORRELATION_ID.get() or "-"
        record.correlation_id = cid

        # Let the base Formatter build the core line.
        base = super().format(record)

        # Append any custom fields from `extra=...` as key=value pairs.
        extras = [
            f"{key}={_format_extra_value(value)}"
            for key, value in sorted(_record_extras(record).items())
        ]

        if extras:
            return f"{base} " + " ".join(extras)
        return base


class JsonLogFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    _time_format = "%Y-%m-%dT%H:%M:%S"

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        pattern = datefmt or self._time_format
        base = dt.strftime(pattern)
        return f"{base}.{int(record.msecs):03d}Z"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - std signature
        cid = getattr(record, "correlation_id", None) or _CORRELATION_ID.get() or "-"
        record.correlation_id = cid
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self._time_format),
            "level": record.levelname,
            "service": "ade-api",
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": cid,
        }
        payload.update(_record_extras(record))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=_json_default, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def setup_logging(settings: Settings) -> None:
    """Configure root logging for the ADE API process.

    This installs a single StreamHandler and sets the API baseline log level
    from ``settings.effective_api_log_level``.

    It also wires common third-party loggers (uvicorn, alembic, sqlalchemy) to
    propagate into the same root logger so that all logs share a consistent
    format and configuration.
    """
    root_logger = logging.getLogger()

    level_name = settings.effective_api_log_level
    level = getattr(logging, level_name)

    configured = getattr(root_logger, _CONFIGURED_FLAG, False)
    if not configured or not root_logger.handlers:
        # Replace existing handlers once to avoid duplicate output.
        root_logger.handlers = [logging.StreamHandler()]
        setattr(root_logger, _CONFIGURED_FLAG, True)
    else:
        # Keep exactly one root handler for deterministic output.
        root_logger.handlers = [root_logger.handlers[0]]

    handler = root_logger.handlers[0]
    handler.setFormatter(_build_formatter(settings.log_format))
    root_logger.setLevel(level)

    # Reset logger-specific overrides, then apply explicit policy.
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "ade_api.request",
        "alembic",
        "alembic.runtime.migration",
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
    ):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        logger.disabled = False
        logger.setLevel(logging.NOTSET)

    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("ade_api.request").setLevel(
        getattr(logging, settings.effective_request_log_level)
    )

    access_logger = logging.getLogger("uvicorn.access")
    if settings.access_log_enabled:
        access_logger.disabled = False
        access_logger.propagate = True
        access_logger.setLevel(getattr(logging, settings.effective_access_log_level))
    else:
        access_logger.handlers.clear()
        access_logger.propagate = False
        access_logger.disabled = True

    # SQLAlchemy logs are noisy in day-to-day dev; default to WARNING.
    # Callers can opt in to SQL traces with ADE_DATABASE_LOG_LEVEL=INFO|DEBUG.
    db_level_name = settings.database_log_level or "WARNING"
    db_level = getattr(logging, db_level_name)
    for name in ("sqlalchemy", "sqlalchemy.engine", "sqlalchemy.pool"):
        logging.getLogger(name).setLevel(db_level)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def bind_request_context(correlation_id: str | None) -> None:
    """Bind a correlation ID to the logging context for the current request."""
    _CORRELATION_ID.set(correlation_id)


def clear_request_context() -> None:
    """Clear the request-scoped logging context."""
    _CORRELATION_ID.set(None)


def current_request_id() -> str | None:
    """Return the current request/correlation ID if bound."""
    return _CORRELATION_ID.get()


def log_context(
    *,
    workspace_id: UUID | str | None = None,
    configuration_id: UUID | str | None = None,
    run_id: UUID | str | None = None,
    document_id: UUID | str | None = None,
    user_id: UUID | str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a consistent `extra` payload for structured logs.

    Example:
        logger.info(
            "run.create.success",
            extra=log_context(
                workspace_id=ws_id,
                configuration_id=cfg_id,
                run_id=run_id,
                user_id=user.id,
            ),
        )
    """
    ctx: dict[str, Any] = {}

    if workspace_id is not None:
        ctx["workspace_id"] = str(workspace_id)
    if configuration_id is not None:
        ctx["configuration_id"] = str(configuration_id)
    if run_id is not None:
        ctx["run_id"] = str(run_id)
    if document_id is not None:
        ctx["document_id"] = str(document_id)
    if user_id is not None:
        ctx["user_id"] = str(user_id)

    # Allow arbitrary additional structured fields.
    for key, value in extra.items():
        ctx[key] = value

    return ctx


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_extra_value(value: Any) -> str:
    """Format an `extra` value for console output."""
    if isinstance(value, (int, float, bool)):
        return str(value)
    if value is None:
        return "null"
    return str(value)


def _record_extras(record: logging.LogRecord) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in _STANDARD_ATTRS or key.startswith("_"):
            continue
        extras[key] = value
    return extras


def _json_default(value: Any) -> str:
    return str(value)


def _build_formatter(log_format: str) -> logging.Formatter:
    if log_format == "json":
        return JsonLogFormatter()
    return ConsoleLogFormatter()


__all__ = [
    "ConsoleLogFormatter",
    "JsonLogFormatter",
    "bind_request_context",
    "clear_request_context",
    "current_request_id",
    "log_context",
    "setup_logging",
]
