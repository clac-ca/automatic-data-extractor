"""Domain event emitters built on top of structured logging."""

from __future__ import annotations

import logging
from typing import Any


class EventLogger:
    """Emit structured domain events, with optional namespace qualification."""

    def __init__(self, logger: logging.Logger | logging.LoggerAdapter, *, namespace: str = "") -> None:
        self._logger = logger
        self._namespace = namespace.rstrip(".")

    def _qualify(self, event_name: str) -> str:
        if not self._namespace:
            return event_name
        prefix = f"{self._namespace}."
        return event_name if event_name.startswith(prefix) else prefix + event_name

    def emit(
        self,
        event_name: str,
        *,
        message: str | None = None,
        level: int = logging.INFO,
        stage: str | None = None,
        **data: Any,
    ) -> None:
        """Emit a domain event as a structured log record.

        Args:
            event_name:
                Stable event name (e.g. ``"table.mapped"``).
            message:
                Optional human-friendly message (defaults to the event name).
            level:
                Standard logging level (INFO by default).
            stage:
                Optional engine stage (top-level field).
            **data:
                Structured payload, stored under ``data`` in NDJSON output.
        """
        full_name = self._qualify(str(event_name))

        extra: dict[str, Any] = {"event": full_name}
        if stage is not None:
            extra["stage"] = str(stage)
        if data:
            extra["data"] = data
        self._logger.log(level, message or full_name, extra=extra)


# Backwards compatibility alias
EventEmitter = EventLogger

__all__ = ["EventEmitter", "EventLogger"]
