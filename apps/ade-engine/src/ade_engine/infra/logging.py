from __future__ import annotations

import logging
from dataclasses import dataclass

from ade_engine.infra.telemetry import EventEmitter


@dataclass(frozen=True)
class RunLogContext:
    """Metadata attached to run-scoped loggers."""

    run_id: str
    config_version: str | None = None


class TelemetryLogHandler(logging.Handler):
    """Bridge Python logging into run console telemetry events."""

    def __init__(self, *, event_emitter: EventEmitter, scope: str = "run") -> None:
        super().__init__()
        self._event_emitter = event_emitter
        self._scope = scope

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = record.levelname.lower()
            stream = "stderr" if record.levelno >= logging.WARNING else "stdout"
            self._event_emitter.console_line(
                message=msg,
                level=level,
                stream=stream,
                scope=self._scope,
                logger=record.name,
                engine_timestamp=record.created,
            )
        except Exception:
            self.handleError(record)


def build_run_logger(
    *, base_name: str, event_emitter: EventEmitter, bridge_to_telemetry: bool = True
) -> logging.Logger:
    """Construct a run-scoped logger optionally bridged to telemetry."""

    logger = logging.getLogger(base_name)
    logger.setLevel(logging.INFO)

    if bridge_to_telemetry and not any(isinstance(h, TelemetryLogHandler) for h in logger.handlers):
        handler = TelemetryLogHandler(event_emitter=event_emitter)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return logger


__all__ = ["RunLogContext", "TelemetryLogHandler", "build_run_logger"]
