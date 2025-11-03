"""Pydantic models for job API payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import JobStatus


class JobSubmitRequest(BaseModel):
    """Request payload for submitting a job."""

    config_version_id: str = Field(..., min_length=1)
    input_hash: str | None = Field(default=None, max_length=128)
    document_ids: list[str] = Field(default_factory=list, description="Document identifiers to stage as inputs")
    document_id: str | None = Field(
        default=None,
        description="Single document identifier convenience field (merged into document_ids)",
    )

    @field_validator("document_ids", mode="before")
    @classmethod
    def _normalise_document_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    @field_validator("document_id", mode="before")
    @classmethod
    def _strip_document_id(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @property
    def all_document_ids(self) -> list[str]:
        items: list[str] = []
        if self.document_id:
            items.append(self.document_id)
        items.extend(self.document_ids)
        seen: set[str] = set()
        unique = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                unique.append(item)
        return unique


class JobConfigVersion(BaseModel):
    """Embedded config version metadata for job responses."""

    config_version_id: str
    config_id: str
    label: str | None = None


class JobRecord(BaseModel):
    """Detailed job response payload."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    job_id: str = Field(alias="id", serialization_alias="job_id")
    workspace_id: str
    status: JobStatus
    artifact_uri: str | None = None
    output_uri: str | None = None
    logs_uri: str | None = None
    run_request_uri: str | None = None
    input_hash: str | None = None
    trace_id: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    attempt: int
    config_version: JobConfigVersion


class JobArtifact(BaseModel):
    """Representation of the job artifact JSON."""

    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)

    schema_: str = Field(alias="schema", serialization_alias="schema")
    artifact_version: str | None = None
    job: dict[str, Any]
    config: dict[str, Any]
    engine: dict[str, Any] | None = None
    rules: dict[str, Any] | None = None
    sheets: list[dict[str, Any]]
    output: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    pass_history: list[dict[str, Any]]
    annotations: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def schema(self) -> str:
        return self.schema_


__all__ = [
    "JobArtifact",
    "JobConfigVersion",
    "JobRecord",
    "JobSubmitRequest",
]
