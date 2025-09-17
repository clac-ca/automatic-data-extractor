"""Pydantic schemas for API responses and payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str


class SnapshotBase(BaseModel):
    """Shared fields for snapshot payloads."""

    document_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    is_published: bool = False

    @model_validator(mode="after")
    def _strip_title(cls, model: "SnapshotBase") -> "SnapshotBase":  # noqa: D401 - simple helper
        """Ensure critical string fields retain non-whitespace characters."""

        if not model.title.strip():
            msg = "title must not be empty or whitespace"
            raise ValueError(msg)
        if not model.document_type.strip():
            msg = "document_type must not be empty or whitespace"
            raise ValueError(msg)
        return model


class SnapshotCreate(SnapshotBase):
    """Payload for creating snapshots."""


class SnapshotUpdate(BaseModel):
    """Payload for updating snapshots."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    payload: dict[str, Any] | None = None
    is_published: bool | None = None

    @model_validator(mode="after")
    def _validate_update(cls, model: "SnapshotUpdate") -> "SnapshotUpdate":
        """Ensure at least one field is supplied and enforce field-specific rules."""

        if not model.model_fields_set:
            msg = "At least one field must be provided"
            raise ValueError(msg)

        if "title" in model.model_fields_set and model.title is not None and not model.title.strip():
            msg = "title must not be empty or whitespace"
            raise ValueError(msg)

        if "payload" in model.model_fields_set and model.payload is None:
            msg = "payload cannot be null"
            raise ValueError(msg)

        return model


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
