"""Typed request/response contracts for job processor integrations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class JobProcessorRequest:
    """Input payload provided to a document extraction processor."""

    job_id: str
    document_path: Path
    configuration: Mapping[str, Any]
    metadata: Mapping[str, Any]


@dataclass(slots=True)
class JobProcessorResult:
    """Structured response returned by a document extraction processor."""

    status: str
    tables: list[dict[str, Any]] = field(default_factory=list)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)


ProcessorCallable = Callable[[JobProcessorRequest], JobProcessorResult]


class ProcessorError(RuntimeError):
    """Raised by processors to indicate business-level failures."""


def _stub_processor(request: JobProcessorRequest) -> JobProcessorResult:
    """Return deterministic tables and metrics for extractor simulations."""

    configuration = dict(request.configuration or {})
    if configuration.get("simulate_failure"):
        message = str(configuration.get("failure_message", "Stub processor failure"))
        raise ProcessorError(message)

    tables = [dict(table) for table in configuration.get("tables", [])]
    metrics = dict(configuration.get("metrics", {}))
    if "tables_produced" not in metrics:
        metrics["tables_produced"] = len(tables)
    if "rows_processed" not in metrics:
        metrics["rows_processed"] = sum(len(table.get("rows", [])) for table in tables)
    logs = [dict(entry) for entry in configuration.get("logs", [])]
    timestamp = datetime.now(tz=UTC).isoformat(timespec="seconds")
    logs.insert(0, {"ts": timestamp, "level": "info", "message": "Processor started"})
    logs.append({"ts": timestamp, "level": "info", "message": "Processor completed"})
    status = str(configuration.get("status", "succeeded"))

    return JobProcessorResult(status=status, tables=tables, metrics=metrics, logs=logs)


_current_processor: ProcessorCallable = _stub_processor


def get_job_processor() -> ProcessorCallable:
    """Return the callable responsible for executing jobs."""

    return _current_processor


def set_job_processor(processor: ProcessorCallable | None) -> None:
    """Override the job processor callable, resetting to the stub when None."""

    global _current_processor
    if processor is None:
        _current_processor = _stub_processor
    else:
        _current_processor = processor


__all__ = [
    "JobProcessorRequest",
    "JobProcessorResult",
    "ProcessorCallable",
    "ProcessorError",
    "get_job_processor",
    "set_job_processor",
]
