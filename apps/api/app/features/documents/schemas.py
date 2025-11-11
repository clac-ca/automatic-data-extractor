"""Pydantic schemas for the documents module."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from apps.api.app.shared.core.ids import ULIDStr
from apps.api.app.shared.core.schema import BaseSchema
from apps.api.app.shared.pagination import Page

from .models import DocumentSource, DocumentStatus


class UploaderSummary(BaseSchema):
    """Minimal representation of the user who uploaded the document."""

    id: ULIDStr = Field(
        description="Uploader ULID (26-character string).",
    )
    name: str | None = Field(
        default=None,
        alias="display_name",
        serialization_alias="name",
        description="Uploader display name when provided.",
    )
    email: str = Field(description="Uploader email address.")


class DocumentRecord(BaseSchema):
    """Serialised representation of a stored document."""

    document_id: ULIDStr = Field(
        alias="id",
        serialization_alias="document_id",
        description="Document ULID (26-character string).",
    )
    workspace_id: ULIDStr
    name: str = Field(
        alias="original_filename",
        serialization_alias="name",
        description="Display name mapped from the original filename.",
    )
    content_type: str | None = None
    byte_size: int
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        alias="attributes",
        serialization_alias="metadata",
    )
    status: DocumentStatus
    source: DocumentSource
    expires_at: datetime
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: ULIDStr | None = Field(
        default=None,
        alias="deleted_by_user_id",
        serialization_alias="deleted_by",
    )
    tags: list[str] = Field(
        default_factory=list,
        alias="tag_values",
        serialization_alias="tags",
        description="Tags applied to the document (empty list when none).",
    )
    uploader: UploaderSummary | None = Field(
        default=None,
        alias="uploaded_by_user",
        serialization_alias="uploader",
        description="Summary of the uploading user when available.",
    )

    @property
    def original_filename(self) -> str:
        """Retain compatibility with existing callers expecting ``original_filename``."""

        return self.name


class DocumentListResponse(Page[DocumentRecord]):
    """Paginated envelope of document records."""


__all__ = ["DocumentListResponse", "DocumentRecord", "UploaderSummary"]
