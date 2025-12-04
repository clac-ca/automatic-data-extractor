"""Infrastructure utilities for IO and telemetry."""

from .io import iter_csv_rows, iter_sheet_rows, list_input_files
from .logging import RunLogContext, TelemetryLogHandler, build_run_logger
from .event_emitter import BaseNdjsonEmitter, ConfigEventEmitter, EngineEventEmitter
from .telemetry import DispatchEventSink, EventSink, FileEventSink, TelemetryConfig

__all__ = [
    "BaseNdjsonEmitter",
    "ConfigEventEmitter",
    "DispatchEventSink",
    "EventSink",
    "EngineEventEmitter",
    "FileEventSink",
    "RunLogContext",
    "TelemetryConfig",
    "TelemetryLogHandler",
    "build_run_logger",
    "iter_csv_rows",
    "iter_sheet_rows",
    "list_input_files",
]
