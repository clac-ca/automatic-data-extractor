"""Pydantic models for document responses."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ...core.schema import BaseSchema


class DocumentDeleteRequest(BaseSchema):
    """Payload accepted when deleting a document."""

    reason: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional explanation recorded alongside the deletion event.",
    )


class DocumentMetadataUpdateRequest(BaseSchema):
    """Payload accepted when updating document metadata."""

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Partial metadata updates to merge into the stored record.",
    )
    event_type: str | None = Field(
        default=None,
        max_length=128,
        description="Optional override for the emitted event type.",
    )
    event_payload: dict[str, Any] | None = Field(
        default=None,
        description="Additional context merged into the event payload.",
    )


class DocumentRecord(BaseSchema):
    """Serialised representation of document metadata."""

    document_id: str = Field(alias="id", serialization_alias="document_id")
    original_filename: str
    content_type: str | None = None
    byte_size: int
    sha256: str
    stored_uri: str
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        alias="metadata_",
        serialization_alias="metadata",
    )
    expires_at: str
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    deleted_by: str | None = None
    delete_reason: str | None = None
    produced_by_job_id: str | None = Field(default=None, serialization_alias="produced_by_job_id")


__all__ = [
    "DocumentDeleteRequest",
    "DocumentMetadataUpdateRequest",
    "DocumentRecord",
]
