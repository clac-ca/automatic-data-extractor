"""Pydantic models for job responses."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field

from ...core.schema import BaseSchema


class JobSubmissionRequest(BaseSchema):
    """Payload accepted when queueing a new processing job."""

    input_document_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        validation_alias=AliasChoices("document_id", "input_document_id"),
        serialization_alias="document_id",
    )
    document_type: str = Field(..., min_length=1, max_length=100)
    configuration_id: str | None = Field(
        default=None,
        min_length=26,
        max_length=26,
    )
    configuration_version: int | None = Field(default=None, ge=1)


class JobRecord(BaseSchema):
    """Serialised representation of job metadata."""

    job_id: str
    document_type: str
    configuration_id: str
    configuration_version: int
    status: str
    created_at: str
    updated_at: str
    created_by: str
    input_document_id: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    logs: list[dict[str, Any]] = Field(default_factory=list)


__all__ = ["JobRecord", "JobSubmissionRequest"]
