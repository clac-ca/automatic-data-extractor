"""Pydantic schemas for the documents module."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ade_api.common.ids import UUIDStr
from ade_api.common.pagination import Page
from ade_api.common.schema import BaseSchema
from ade_api.models import (
    DocumentSource,
    DocumentStatus,
    DocumentUploadConflictBehavior,
    DocumentUploadSessionStatus,
    RunStatus,
)


class DocumentDisplayStatus(str, Enum):
    """UI-friendly status derived from document + run state."""

    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentQueueState(str, Enum):
    """Queue lifecycle for documents that are not yet processing."""

    WAITING = "waiting"
    QUEUED = "queued"


class DocumentQueueReason(str, Enum):
    """Reason for documents waiting to enter the run queue."""

    NO_ACTIVE_CONFIGURATION = "no_active_configuration"
    QUEUE_FULL = "queue_full"
    PROCESSING_PAUSED = "processing_paused"


def _fallback_display_status(status: DocumentStatus) -> DocumentDisplayStatus:
    if status == DocumentStatus.ARCHIVED:
        return DocumentDisplayStatus.ARCHIVED
    if status == DocumentStatus.FAILED:
        return DocumentDisplayStatus.FAILED
    if status == DocumentStatus.PROCESSED:
        return DocumentDisplayStatus.READY
    if status == DocumentStatus.PROCESSING:
        return DocumentDisplayStatus.PROCESSING
    return DocumentDisplayStatus.QUEUED


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
    display_status: DocumentDisplayStatus = DocumentDisplayStatus.QUEUED
    queue_state: DocumentQueueState | None = None
    queue_reason: DocumentQueueReason | None = None
    source: DocumentSource
    expires_at: datetime
    last_run_at: datetime | None = None
    activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    assignee_user_id: UUIDStr | None = None
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

    @model_validator(mode="after")
    def _derive_defaults(self) -> "DocumentOut":
        if self.activity_at is None:
            candidate = self.updated_at
            if self.last_run_at is not None and self.last_run_at > candidate:
                candidate = self.last_run_at
            self.activity_at = candidate
        if self.display_status is None:
            self.display_status = _fallback_display_status(self.status)
        return self


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
    def _ensure_changes(self) -> DocumentTagsPatch:
        if not (self.add or self.remove):
            raise ValueError("add or remove is required")
        return self


class DocumentUpdateRequest(BaseSchema):
    """Payload for updating document metadata or assignment."""

    assignee_user_id: UUIDStr | None = Field(
        default=None,
        description="Assign the document to a user (null clears assignment).",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Replace the document metadata payload.",
    )

    @model_validator(mode="after")
    def _ensure_changes(self) -> "DocumentUpdateRequest":
        assignee_set = "assignee_user_id" in self.model_fields_set
        if not assignee_set and self.metadata is None:
            raise ValueError("assignee_user_id or metadata is required")
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
    def _ensure_changes(self) -> DocumentBatchTagsRequest:
        if not (self.add or self.remove):
            raise ValueError("add or remove is required")
        return self


class DocumentBatchTagsResponse(BaseSchema):
    """Response envelope for batch tag updates."""

    documents: list[DocumentOut] = Field(default_factory=list)


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


class DocumentBatchArchiveRequest(BaseSchema):
    """Payload for archiving or restoring multiple documents."""

    document_ids: list[UUIDStr] = Field(
        ...,
        min_length=1,
        description="Documents to archive or restore (all-or-nothing).",
    )


class DocumentBatchArchiveResponse(BaseSchema):
    """Response envelope for batch archive or restore operations."""

    documents: list[DocumentOut] = Field(default_factory=list)


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

    changes_cursor: str = Field(
        description="Watermark cursor for the documents change feed at response time.",
    )


class DocumentChangeEntry(BaseSchema):
    """Single entry from the documents change feed."""

    cursor: str
    type: Literal["document.upsert", "document.deleted"]
    document: DocumentOut | None = None
    document_id: UUIDStr | None = None
    occurred_at: datetime

    @model_validator(mode="after")
    def _validate_payload(self) -> "DocumentChangeEntry":
        if self.type == "document.deleted" and not self.document_id:
            raise ValueError("document_id is required for document.deleted changes")
        if self.type == "document.upsert" and self.document is None:
            raise ValueError("document is required for document.upsert changes")
        return self


class DocumentChangesPage(BaseSchema):
    """Envelope for cursor-based change feed results."""

    changes: list[DocumentChangeEntry] = Field(default_factory=list)
    next_cursor: str


class DocumentUploadSessionCreateRequest(BaseSchema):
    """Create a resumable upload session for a document."""

    filename: str
    byte_size: int = Field(ge=1)
    content_type: str | None = None
    conflict_behavior: DocumentUploadConflictBehavior = DocumentUploadConflictBehavior.RENAME
    folder_id: str | None = None
    metadata: dict[str, Any] | None = None


class DocumentUploadSessionCreateResponse(BaseSchema):
    """Response payload for a new upload session."""

    upload_session_id: UUIDStr
    expires_at: datetime
    chunk_size_bytes: int
    next_expected_ranges: list[str]
    upload_url: str


class DocumentUploadSessionStatusResponse(BaseSchema):
    """Status payload for an upload session."""

    upload_session_id: UUIDStr
    expires_at: datetime
    byte_size: int
    received_bytes: int
    next_expected_ranges: list[str]
    upload_complete: bool = False
    status: DocumentUploadSessionStatus


class DocumentUploadSessionUploadResponse(BaseSchema):
    """Response payload after uploading a range."""

    next_expected_ranges: list[str]
    upload_complete: bool = False


class DocumentSheet(BaseSchema):
    """Descriptor for a worksheet or single-sheet document."""

    name: str
    index: int = Field(ge=0)
    kind: Literal["worksheet", "file"] = "worksheet"
    is_active: bool = False


__all__ = [
    "DocumentBatchArchiveRequest",
    "DocumentBatchArchiveResponse",
    "DocumentBatchDeleteRequest",
    "DocumentBatchDeleteResponse",
    "DocumentBatchTagsRequest",
    "DocumentBatchTagsResponse",
    "DocumentChangeEntry",
    "DocumentChangesPage",
    "DocumentDisplayStatus",
    "DocumentQueueReason",
    "DocumentQueueState",
    "DocumentLastRun",
    "DocumentOut",
    "DocumentPage",
    "DocumentSheet",
    "DocumentTagsPatch",
    "DocumentTagsReplace",
    "DocumentUpdateRequest",
    "DocumentUploadSessionCreateRequest",
    "DocumentUploadSessionCreateResponse",
    "DocumentUploadSessionStatusResponse",
    "DocumentUploadSessionUploadResponse",
    "TagCatalogItem",
    "TagCatalogPage",
    "UploaderOut",
]
