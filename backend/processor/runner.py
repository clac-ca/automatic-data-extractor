"""Deterministic stub implementation for the extraction processor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ProcessorError(RuntimeError):
    """Raised when the stub processor encounters an unrecoverable error."""


@dataclass(slots=True)
class JobRequest:
    """Inputs provided to the processor when executing a job."""

    job_id: str
    document_path: Path
    configuration: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class JobResult:
    """Structured payload returned by the processor upon completion."""

    status: str
    metrics: Mapping[str, Any] = field(default_factory=dict)
    logs: Sequence[Mapping[str, Any]] = field(default_factory=list)
    tables: Sequence[Mapping[str, Any]] = field(default_factory=list)


def run(job_request: JobRequest) -> JobResult:
    """Execute the deterministic extraction stub for ``job_request``."""

    document_path = job_request.document_path
    if not document_path.exists():
        raise ProcessorError(f"Document '{document_path}' is not available")

    configuration = dict(job_request.configuration or {})
    if configuration.get("simulate_failure"):
        message = configuration.get("failure_message") or "Extractor simulation failed"
        raise ProcessorError(str(message))

    tables = list(configuration.get("tables") or [])
    if not tables:
        tables = [
            {
                "title": "Stub output",
                "columns": ["source", "job_id"],
                "rows": [
                    {"source": document_path.name, "job_id": job_request.job_id},
                ],
                "sequence_index": 0,
                "metadata": {
                    "generator": "stub",
                    "document_path": str(document_path),
                },
            }
        ]

    metrics = dict(configuration.get("metrics") or {})
    if not metrics:
        total_rows = sum(len(table.get("rows") or []) for table in tables)
        metrics = {
            "rows_processed": total_rows,
            "tables_produced": len(tables),
        }

    logs = list(configuration.get("logs") or [])
    timestamp = datetime.now(tz=UTC).isoformat(timespec="seconds")
    logs.insert(0, {"ts": timestamp, "level": "info", "message": "Job started"})
    logs.append({"ts": timestamp, "level": "info", "message": "Job completed"})

    return JobResult(status="succeeded", metrics=metrics, logs=logs, tables=tables)


__all__ = ["JobRequest", "JobResult", "ProcessorError", "run"]
