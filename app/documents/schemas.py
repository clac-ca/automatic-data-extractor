"""Pydantic schemas for the documents module."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.core.schema import BaseSchema


class DocumentRecord(BaseSchema):
    """Serialised representation of a stored document."""

    document_id: str = Field(alias="id", serialization_alias="document_id")
    workspace_id: str
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


class DocumentDeleteRequest(BaseSchema):
    """Optional reason provided when soft-deleting a document."""

    reason: str | None = Field(default=None, max_length=1024)


__all__ = ["DocumentDeleteRequest", "DocumentRecord"]
