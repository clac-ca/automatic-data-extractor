from __future__ import annotations

import logging
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from ade_engine.infrastructure.observability.formatters import NdjsonFormatter, TextFormatter
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.models.events import ENGINE_NAMESPACE


@dataclass
class RunLogContext:
    logger: RunLogger
    _base_logger: logging.Logger
    _handlers: list[logging.Handler]

    def close(self) -> None:
        for h in list(self._handlers):
            try:
                self._base_logger.removeHandler(h)
                h.close()
            except Exception:
                pass

    def __enter__(self) -> "RunLogContext":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()


def create_run_logger_context(
    *,
    namespace: str = ENGINE_NAMESPACE,
    log_format: str = "text",
    log_level: int = logging.INFO,
    enable_console_logging: bool = True,
    log_file: Path | None = None,
) -> RunLogContext:
    fmt = (log_format or "text").strip().lower()
    if fmt == "json":
        fmt = "ndjson"
    if fmt not in {"text", "ndjson"}:
        raise ValueError("log_format must be 'text' or 'ndjson' (or 'json')")

    formatter: logging.Formatter = NdjsonFormatter() if fmt == "ndjson" else TextFormatter()

    handlers: list[logging.Handler] = []

    if enable_console_logging:
        h = logging.StreamHandler(sys.stderr)
        h.setLevel(log_level)
        h.setFormatter(formatter)
        handlers.append(h)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        handlers.append(fh)

    run_id = uuid.uuid4().hex
    base_logger = logging.getLogger(f"ade_engine.run.{run_id}")
    base_logger.setLevel(log_level)
    base_logger.handlers.clear()
    base_logger.propagate = False
    for h in handlers:
        base_logger.addHandler(h)

    logger = RunLogger(base_logger, namespace=namespace, engine_run_id=run_id)
    return RunLogContext(logger=logger, _base_logger=base_logger, _handlers=handlers)


__all__ = [
    "RunLogContext",
    "create_run_logger_context",
]

