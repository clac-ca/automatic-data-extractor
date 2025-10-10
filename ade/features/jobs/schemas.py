"""Pydantic schemas for the jobs module."""

from __future__ import annotations

from typing import Any

from datetime import datetime

from pydantic import Field

from ade.core.schema import BaseSchema


class JobFailureDetail(BaseSchema):
    """Structured payload returned when a job execution fails."""

    error: str
    job_id: str
    message: str


class JobFailureMessage(BaseSchema):
    """Error envelope that wraps :class:`JobFailureDetail`."""

    detail: JobFailureDetail


class JobSubmissionRequest(BaseSchema):
    """Payload accepted when clients submit a new job."""

    input_document_id: str
    configuration_id: str
    configuration_version: int | None = None


class JobRecord(BaseSchema):
    """Serialised representation of a job row."""

    job_id: str
    workspace_id: str
    document_type: str
    configuration_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    created_by_user_id: str | None = None
    input_document_id: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    logs: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "JobFailureDetail",
    "JobFailureMessage",
    "JobRecord",
    "JobSubmissionRequest",
]
