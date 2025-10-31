"""Pydantic schemas for the jobs module."""

from __future__ import annotations

from typing import Any

from datetime import datetime

from pydantic import Field

from backend.app.shared.core.schema import BaseSchema


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
    config_id: str | None = None


class JobRecord(BaseSchema):
    """Serialised representation of a job row."""

    job_id: str
    workspace_id: str
    config_id: str
    config_files_hash: str | None = None
    config_package_sha256: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    created_by_user_id: str | None = None
    input_document_id: str
    run_key: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    logs: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "JobFailureDetail",
    "JobFailureMessage",
    "JobRecord",
    "JobSubmissionRequest",
]
