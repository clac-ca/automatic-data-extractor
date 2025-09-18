"""Pydantic schemas for API responses and payloads."""

from __future__ import annotations

from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator
from pydantic.types import StringConstraints


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str


class DocumentResponse(BaseModel):
    """API representation of stored document metadata."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str
    original_filename: str
    content_type: str | None = None
    byte_size: int
    sha256: str
    stored_uri: str = Field(
        description=(
            "Relative storage path anchored under the configured documents directory"
        )
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    expires_at: str
    created_at: str
    updated_at: str

    @field_serializer("stored_uri")
    def _serialise_stored_uri(self, stored_uri: str) -> str:
        """Return a canonical relative URI for the stored document."""

        _, _, digest = self.sha256.partition(":")
        digest = digest or self.sha256
        if not digest:
            return stored_uri.replace("\\", "/")

        first = digest[:2]
        second = digest[2:4]
        parts = [first]
        if second:
            parts.append(second)
        parts.append(digest)
        return "/".join(parts)


class ConfigurationRevisionBase(BaseModel):
    """Shared fields for configuration revision payloads."""

    document_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = False


class ConfigurationRevisionCreate(ConfigurationRevisionBase):
    """Payload for creating configuration revisions."""


class ConfigurationRevisionUpdate(BaseModel):
    """Payload for updating configuration revisions."""

    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ] | None = None
    payload: dict[str, Any] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _ensure_updates(self) -> "ConfigurationRevisionUpdate":
        if "payload" in self.model_fields_set and self.payload is None:
            msg = "payload cannot be null"
            raise ValueError(msg)
        if "is_active" in self.model_fields_set and self.is_active is None:
            msg = "is_active cannot be null"
            raise ValueError(msg)
        if not self.model_fields_set:
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return self


class ConfigurationRevisionResponse(BaseModel):
    """API response model for configuration revision resources."""

    model_config = ConfigDict(from_attributes=True)

    configuration_revision_id: str
    document_type: str
    title: str
    payload: dict[str, Any]
    revision_number: int
    is_active: bool
    activated_at: str | None = None
    created_at: str
    updated_at: str


JobStatus = Literal["pending", "running", "completed", "failed"]


class JobInput(BaseModel):
    """Input document metadata captured on each job."""

    uri: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
    ]
    hash: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    expires_at: str


class JobOutputReference(BaseModel):
    """Reference to a generated output artifact."""

    uri: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
    ]
    expires_at: str


class JobMetrics(BaseModel):
    """Summary statistics emitted by a job."""

    model_config = ConfigDict(extra="allow")

    rows_extracted: int | None = None
    processing_time_ms: int | None = None
    errors: int | None = None


class JobLogEntry(BaseModel):
    """Structured log entry captured while a job runs."""

    ts: str
    level: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16)
    ]
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1024)
    ]


class JobCreate(BaseModel):
    """Payload for creating a processing job."""

    document_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    created_by: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    input: JobInput
    status: JobStatus = "pending"
    configuration_revision_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=26, max_length=26)
    ] | None = None
    outputs: dict[str, JobOutputReference] = Field(default_factory=dict)
    metrics: JobMetrics = Field(default_factory=JobMetrics)
    logs: list[JobLogEntry] = Field(default_factory=list)


class JobUpdate(BaseModel):
    """Payload for mutating a job while it is running."""

    status: JobStatus | None = None
    outputs: dict[str, JobOutputReference] | None = None
    metrics: JobMetrics | None = None
    logs: list[JobLogEntry] | None = None

    @model_validator(mode="after")
    def _ensure_non_empty(self) -> "JobUpdate":
        if not self.model_fields_set:
            msg = "At least one field must be provided"
            raise ValueError(msg)
        if "status" in self.model_fields_set and self.status is None:
            msg = "status cannot be null"
            raise ValueError(msg)
        if "outputs" in self.model_fields_set and self.outputs is None:
            msg = "outputs cannot be null"
            raise ValueError(msg)
        if "metrics" in self.model_fields_set and self.metrics is None:
            msg = "metrics cannot be null"
            raise ValueError(msg)
        if "logs" in self.model_fields_set and self.logs is None:
            msg = "logs cannot be null"
            raise ValueError(msg)
        return self


class JobResponse(BaseModel):
    """API representation of a job record."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str
    document_type: str
    configuration_revision: int = Field(validation_alias="configuration_revision_number")
    status: JobStatus
    created_at: str
    updated_at: str
    created_by: str
    input: JobInput
    outputs: dict[str, JobOutputReference] = Field(default_factory=dict)
    metrics: JobMetrics = Field(default_factory=JobMetrics)
    logs: list[JobLogEntry] = Field(default_factory=list)

__all__ = [
    "HealthResponse",
    "DocumentResponse",
    "ConfigurationRevisionCreate",
    "ConfigurationRevisionUpdate",
    "ConfigurationRevisionResponse",
    "JobStatus",
    "JobInput",
    "JobOutputReference",
    "JobMetrics",
    "JobLogEntry",
    "JobCreate",
    "JobUpdate",
    "JobResponse",
]
