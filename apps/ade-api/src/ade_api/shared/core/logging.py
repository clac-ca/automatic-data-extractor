"""Logging configuration and helpers for the ADE API backend.

This module configures console-style logging for the entire process and exposes
helpers for:

* binding a request-scoped correlation ID, and
* building consistent `extra` payloads for structured logs.

Everything uses the standard :mod:`logging` library. The only customization is
the formatter, which renders one human-readable line per log record, including
timestamp, level, logger name, correlation ID, and any `extra` fields as
``key=value`` pairs.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

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
        extras: list[str] = []
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            extras.append(f"{key}={_format_extra_value(value)}")

        if extras:
            return f"{base} " + " ".join(extras)
        return base


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def setup_logging(settings: Settings) -> None:
    """Configure root logging for the ADE API process.

    This installs a single console-style StreamHandler on stdout and sets the
    root log level from ``settings.logging_level`` (env: ``ADE_LOGGING_LEVEL``).

    It also wires common third-party loggers (uvicorn, alembic, sqlalchemy) to
    propagate into the same root logger so that all logs share a consistent
    format and configuration.
    """
    root_logger = logging.getLogger()

    level_name = settings.logging_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    # Only fully configure once per process; subsequent calls just adjust level.
    if getattr(root_logger, _CONFIGURED_FLAG, False):
        root_logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(ConsoleLogFormatter())

    # Replace any existing handlers to avoid duplicate logs.
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Let common third-party loggers propagate into our root logger.
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "alembic",
        "alembic.runtime.migration",
        "sqlalchemy",
    ):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    setattr(root_logger, _CONFIGURED_FLAG, True)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def bind_request_context(correlation_id: str | None) -> None:
    """Bind a correlation ID to the logging context for the current request."""
    _CORRELATION_ID.set(correlation_id)


def clear_request_context() -> None:
    """Clear the request-scoped logging context."""
    _CORRELATION_ID.set(None)


def log_context(
    *,
    workspace_id: str | None = None,
    configuration_id: str | None = None,
    run_id: str | None = None,
    build_id: str | None = None,
    document_id: str | None = None,
    user_id: str | None = None,
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
        ctx["workspace_id"] = workspace_id
    if configuration_id is not None:
        ctx["configuration_id"] = configuration_id
    if run_id is not None:
        ctx["run_id"] = run_id
    if build_id is not None:
        ctx["build_id"] = build_id
    if document_id is not None:
        ctx["document_id"] = document_id
    if user_id is not None:
        ctx["user_id"] = user_id

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


__all__ = [
    "ConsoleLogFormatter",
    "bind_request_context",
    "clear_request_context",
    "log_context",
    "setup_logging",
]
