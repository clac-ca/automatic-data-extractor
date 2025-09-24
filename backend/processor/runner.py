"""Scaffolding for the ADE document extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class ExtractionContext:
    """Inputs required to execute the extraction pipeline."""

    job_id: str
    document_id: str
    document_type: str
    configuration_id: str
    configuration_version: int


@dataclass(slots=True)
class ExtractionLogEntry:
    """Structured log entry emitted during extraction."""

    level: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Render the log entry as a plain dictionary for persistence."""

        payload: dict[str, Any] = {"level": self.level, "message": self.message}
        if self.details:
            payload["details"] = dict(self.details)
        return payload


@dataclass(slots=True)
class ExtractionResult:
    """Outcome of executing the extraction pipeline."""

    metrics: Mapping[str, Any] = field(default_factory=dict)
    logs: list[ExtractionLogEntry] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)

    def as_job_logs(self) -> list[dict[str, Any]]:
        """Return log entries serialised for storage on the job record."""

        return [entry.to_dict() for entry in self.logs]


class ExtractionError(Exception):
    """Raised when the extraction pipeline fails to process a document."""


async def run_extraction(context: ExtractionContext) -> ExtractionResult:
    """Execute the extraction pipeline for ``context``."""

    log = ExtractionLogEntry(
        level="info",
        message="Extraction pipeline stub executed.",
        details={
            "job_id": context.job_id,
            "document_id": context.document_id,
            "document_type": context.document_type,
        },
    )

    rows = [
        {"field": "job_id", "value": context.job_id},
        {"field": "document_id", "value": context.document_id},
        {"field": "configuration_version", "value": context.configuration_version},
    ]
    outputs = [
        {
            "title": f"{context.document_type.replace('_', ' ').title()} summary",
            "sequence_index": 0,
            "columns": ["field", "value"],
            "rows": rows,
            "metadata": {
                "stub": True,
                "document_type": context.document_type,
            },
        }
    ]

    metrics = {
        "document_type": context.document_type,
        "tables_detected": len(outputs),
        "pages_processed": 0,
    }
    return ExtractionResult(metrics=metrics, logs=[log], outputs=outputs)


__all__ = [
    "ExtractionContext",
    "ExtractionError",
    "ExtractionLogEntry",
    "ExtractionResult",
    "run_extraction",
]
