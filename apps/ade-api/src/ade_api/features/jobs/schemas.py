"""Shared Pydantic schemas for job representations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.shared.core.ids import ULIDStr
from ade_api.shared.core.schema import BaseSchema

JobStatusLiteral = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class JobSubmissionRequest(BaseSchema):
    """Payload accepted when enqueuing a new job."""

    input_document_id: ULIDStr = Field(description="Document ULID to process.")
    config_version_id: str = Field(description="Configuration version identifier.")
    options: RunCreateOptions = Field(default_factory=RunCreateOptions)


class JobInputDocument(BaseSchema):
    """Minimal representation of a document attached to a job."""

    document_id: ULIDStr
    display_name: str | None = None
    name: str | None = None
    original_filename: str | None = None
    content_type: str | None = None
    byte_size: int | None = None


class JobConfigVersion(BaseSchema):
    """Descriptor for the configuration version used by a job."""

    config_version_id: str
    title: str | None = None
    semver: str | None = None


class JobSubmittedBy(BaseSchema):
    """Subset of user fields for the submitting actor."""

    id: ULIDStr
    display_name: str | None = None
    email: str | None = None


class JobRecord(BaseSchema):
    """API representation of a persisted job."""

    id: ULIDStr
    workspace_id: ULIDStr
    config_id: ULIDStr
    config_version_id: str
    status: JobStatusLiteral
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    updated_at: datetime
    input_documents: list[JobInputDocument] = Field(default_factory=list)
    config_title: str | None = None
    config_version: JobConfigVersion | None = None
    submitted_by_user: JobSubmittedBy | None = None
    submitted_by: str | None = None
    error_message: str | None = None
    summary: str | None = None
    artifact_uri: str | None = None
    logs_uri: str | None = None
    output_uri: str | None = None


class JobOutputFile(BaseSchema):
    """Single file emitted by a job output directory."""

    path: str
    byte_size: int


class JobOutputListing(BaseSchema):
    """Collection of files produced by a job run."""

    files: list[JobOutputFile] = Field(default_factory=list)


__all__ = [
    "JobConfigVersion",
    "JobInputDocument",
    "JobRecord",
    "JobStatusLiteral",
    "JobSubmissionRequest",
    "JobSubmittedBy",
    "JobOutputFile",
    "JobOutputListing",
]
