"""Pydantic schemas for API responses and payloads."""

from __future__ import annotations

from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.types import StringConstraints


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str


TrimmedDocumentType = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
TrimmedTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class SnapshotBase(BaseModel):
    """Shared fields for snapshot payloads."""

    document_type: TrimmedDocumentType
    title: TrimmedTitle
    payload: dict[str, Any] = Field(default_factory=dict)
    is_published: bool = False


class SnapshotCreate(SnapshotBase):
    """Payload for creating snapshots."""


class SnapshotUpdate(BaseModel):
    """Payload for updating snapshots."""

    title: TrimmedTitle | None = None
    payload: dict[str, Any] | None = None
    is_published: bool | None = None

    @model_validator(mode="after")
    def _ensure_updates(self) -> "SnapshotUpdate":
        if "payload" in self.model_fields_set and self.payload is None:
            msg = "payload cannot be null"
            raise ValueError(msg)
        if "is_published" in self.model_fields_set and self.is_published is None:
            msg = "is_published cannot be null"
            raise ValueError(msg)
        if not self.model_fields_set:
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return self


class SnapshotResponse(BaseModel):
    """API response model for snapshot resources."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    document_type: str
    title: str
    payload: dict[str, Any]
    is_published: bool
    created_at: str
    updated_at: str


__all__ = [
    "HealthResponse",
    "SnapshotCreate",
    "SnapshotUpdate",
    "SnapshotResponse",
]
