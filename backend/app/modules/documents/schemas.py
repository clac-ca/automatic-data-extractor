"""Pydantic models for document responses."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ...core.schema import BaseSchema


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


__all__ = ["DocumentRecord"]
