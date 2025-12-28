"""Pydantic schemas for the documents module."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ade_api.common.ids import UUIDStr
from ade_api.common.pagination import Page
from ade_api.common.schema import BaseSchema
from ade_api.models import DocumentSource, DocumentStatus, RunStatus


class UploaderOut(BaseSchema):
    """Minimal representation of the user who uploaded the document."""

    id: UUIDStr = Field(
        description="Uploader UUID (RFC 9562 UUIDv7).",
    )
    name: str | None = Field(
        default=None,
        alias="display_name",
        serialization_alias="name",
        description="Uploader display name when provided.",
    )
    email: str = Field(description="Uploader email address.")


class DocumentOut(BaseSchema):
    """Serialised representation of a stored document."""

    id: UUIDStr = Field(description="Document UUIDv7 (RFC 9562).")
    workspace_id: UUIDStr
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
    deleted_by: UUIDStr | None = Field(
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
    uploader: UploaderOut | None = Field(
        default=None,
        alias="uploaded_by_user",
        serialization_alias="uploader",
        description="Summary of the uploading user when available.",
    )
    last_run: DocumentLastRun | None = Field(
        default=None,
        description="Latest run execution associated with the document when available.",
    )
    last_successful_run: DocumentLastRun | None = Field(
        default=None,
        description="Latest successful run execution associated with the document when available.",
    )

    @field_validator("tags", mode="before")
    @classmethod
    def _sort_tags(cls, value: Any) -> list[str]:
        if not value:
            return []
        return sorted(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def _strip_internal_metadata(cls, value: Any) -> dict[str, Any]:
        """Remove internal attributes such as cached worksheets from API payloads."""

        if isinstance(value, Mapping):
            data = dict(value)
        else:
            data = {}
        data.pop("worksheets", None)
        return data


class DocumentTagsReplace(BaseSchema):
    """Payload for replacing tags on a document."""

    tags: list[str] = Field(
        ...,
        description="Complete set of tags for the document.",
    )


class DocumentTagsPatch(BaseSchema):
    """Payload for adding/removing tags on a document."""

    add: list[str] | None = Field(
        default=None,
        description="Tags to add to the document.",
    )
    remove: list[str] | None = Field(
        default=None,
        description="Tags to remove from the document.",
    )

    @model_validator(mode="after")
    def _ensure_changes(self) -> "DocumentTagsPatch":
        if not (self.add or self.remove):
            raise ValueError("add or remove is required")
        return self


class DocumentBatchTagsRequest(BaseSchema):
    """Payload for updating tags on multiple documents."""

    document_ids: list[UUIDStr] = Field(
        ...,
        min_length=1,
        description="Documents to update tags for (all-or-nothing).",
    )
    add: list[str] | None = Field(
        default=None,
        description="Tags to add to each document.",
    )
    remove: list[str] | None = Field(
        default=None,
        description="Tags to remove from each document.",
    )

    @model_validator(mode="after")
    def _ensure_changes(self) -> "DocumentBatchTagsRequest":
        if not (self.add or self.remove):
            raise ValueError("add or remove is required")
        return self


class DocumentBatchTagsResponse(BaseSchema):
    """Response envelope for batch tag updates."""

    documents: list["DocumentOut"] = Field(default_factory=list)


class DocumentBatchDeleteRequest(BaseSchema):
    """Payload for soft-deleting multiple documents."""

    document_ids: list[UUIDStr] = Field(
        ...,
        min_length=1,
        description="Documents to delete (soft delete, all-or-nothing).",
    )


class DocumentBatchDeleteResponse(BaseSchema):
    """Response envelope for batch deletions."""

    document_ids: list[UUIDStr] = Field(default_factory=list)


class TagCatalogItem(BaseSchema):
    """Tag entry with document counts."""

    tag: str
    document_count: int = Field(ge=0)


class TagCatalogPage(Page[TagCatalogItem]):
    """Paginated tag catalog."""


class DocumentLastRun(BaseSchema):
    """Minimal representation of the last engine execution for a document."""

    run_id: UUIDStr = Field(description="Latest run identifier for the execution.")
    status: RunStatus
    run_at: datetime | None = Field(
        default=None,
        description="Timestamp for the latest run event (completion/start).",
    )
    message: str | None = Field(
        default=None,
        description="Optional status or error message associated with the execution.",
    )


class DocumentPage(Page[DocumentOut]):
    """Paginated envelope of document records."""


class DocumentSheet(BaseSchema):
    """Descriptor for a worksheet or single-sheet document."""

    name: str
    index: int = Field(ge=0)
    kind: Literal["worksheet", "file"] = "worksheet"
    is_active: bool = False


__all__ = [
    "DocumentBatchDeleteRequest",
    "DocumentBatchDeleteResponse",
    "DocumentBatchTagsRequest",
    "DocumentBatchTagsResponse",
    "DocumentLastRun",
    "DocumentOut",
    "DocumentPage",
    "DocumentSheet",
    "DocumentTagsPatch",
    "DocumentTagsReplace",
    "TagCatalogItem",
    "TagCatalogPage",
    "UploaderOut",
]
