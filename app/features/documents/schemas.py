"""Pydantic schemas for the documents module."""

from __future__ import annotations

from datetime import datetime
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
        alias="attributes",
        serialization_alias="metadata",
    )
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: str | None = Field(
        default=None,
        alias="deleted_by_user_id",
        serialization_alias="deleted_by",
    )


__all__ = ["DocumentRecord"]
