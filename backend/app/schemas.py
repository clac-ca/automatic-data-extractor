"""Pydantic schemas for API responses and payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str


class SnapshotBase(BaseModel):
    """Shared fields for snapshot payloads."""

    document_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    is_published: bool = False

    def model_post_init(self, __context: Any) -> None:  # noqa: D401 - simple post-init normalisation
        """Trim string fields and ensure they remain non-empty."""

        super().model_post_init(__context)
        title = self.title.strip()
        if not title:
            msg = "title must not be empty or whitespace"
            raise ValueError(msg)
        document_type = self.document_type.strip()
        if not document_type:
            msg = "document_type must not be empty or whitespace"
            raise ValueError(msg)

        self.title = title
        self.document_type = document_type


class SnapshotCreate(SnapshotBase):
    """Payload for creating snapshots."""


class SnapshotUpdate(BaseModel):
    """Payload for updating snapshots."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    payload: dict[str, Any] | None = None
    is_published: bool | None = None

    def model_post_init(self, __context: Any) -> None:  # noqa: D401 - simple post-init normalisation
        """Normalise and validate optional update fields."""

        super().model_post_init(__context)

        if not self.model_fields_set:
            msg = "At least one field must be provided"
            raise ValueError(msg)

        if "title" in self.model_fields_set:
            if self.title is None:
                msg = "title must not be empty or whitespace"
                raise ValueError(msg)
            title = self.title.strip()
            if not title:
                msg = "title must not be empty or whitespace"
                raise ValueError(msg)
            self.title = title

        if "payload" in self.model_fields_set and self.payload is None:
            msg = "payload cannot be null"
            raise ValueError(msg)

        if "is_published" in self.model_fields_set and self.is_published is None:
            msg = "is_published cannot be null"
            raise ValueError(msg)


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
