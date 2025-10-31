"""Pydantic models for job API payloads."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import JobStatus


class JobSubmitRequest(BaseModel):
    """Request payload for submitting a job."""

    config_version_id: str = Field(..., min_length=1)


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
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    config_version: JobConfigVersion


class JobArtifact(BaseModel):
    """Representation of the job artifact JSON."""

    job: dict[str, Any]
    config: dict[str, Any]
    passes: list[dict[str, Any]]


__all__ = [
    "JobArtifact",
    "JobConfigVersion",
    "JobRecord",
    "JobSubmitRequest",
]
