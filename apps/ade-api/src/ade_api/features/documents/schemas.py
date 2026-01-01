"""Pydantic schemas for the documents module."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ade_api.common.ids import UUIDStr
from ade_api.common.listing import ListPage
from ade_api.common.schema import BaseSchema
from ade_api.models import (
    DocumentSource,
    DocumentStatus,
    DocumentUploadConflictBehavior,
    DocumentUploadSessionStatus,
    RunStatus,
)


class DocumentFileType(str, Enum):
    """Normalized file types for documents."""

    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    PDF = "pdf"
    UNKNOWN = "unknown"


class UserSummary(BaseSchema):
    """Minimal representation of a user for list/detail payloads."""

    id: UUIDStr = Field(
        description="User UUID (RFC 9562 UUIDv7).",
    )
    name: str | None = Field(
        default=None,
        alias="display_name",
        serialization_alias="name",
        description="Display name when provided.",
    )
    email: str = Field(description="User email address.")


class DocumentOut(BaseSchema):
    """Serialised representation of a stored document."""

    id: UUIDStr = Field(description="Document UUIDv7 (RFC 9562).")
    workspace_id: UUIDStr = Field(alias="workspaceId")
    name: str = Field(
        alias="original_filename",
        serialization_alias="name",
        description="Display name mapped from the original filename.",
    )
    content_type: str | None = Field(default=None, alias="contentType")
    byte_size: int = Field(alias="byteSize")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        alias="attributes",
        serialization_alias="metadata",
    )
    status: DocumentStatus
    source: DocumentSource
    expires_at: datetime = Field(alias="expiresAt")
    activity_at: datetime | None = Field(default=None, alias="activityAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    deleted_at: datetime | None = Field(default=None, alias="deletedAt")
    assignee_user_id: UUIDStr | None = Field(default=None, alias="assigneeId")
    deleted_by: UUIDStr | None = Field(
        default=None,
        alias="deleted_by_user_id",
        serialization_alias="deletedBy",
    )
    tags: list[str] = Field(
        default_factory=list,
        alias="tag_values",
        serialization_alias="tags",
        description="Tags applied to the document (empty list when none).",
    )
    uploader: UserSummary | None = Field(
        default=None,
        alias="uploaded_by_user",
        serialization_alias="uploader",
        description="Summary of the uploading user when available.",
    )
    assignee: UserSummary | None = Field(
        default=None,
        alias="assignee_user",
        serialization_alias="assignee",
        description="Summary of the assigned user when available.",
    )
    latest_run: DocumentRunSummary | None = Field(
        default=None,
        alias="latestRun",
        description="Latest run execution associated with the document when available.",
    )
    latest_successful_run: DocumentRunSummary | None = Field(
        default=None,
        alias="latestSuccessfulRun",
        description="Latest successful run execution associated with the document when available.",
    )
    latest_result: DocumentResultSummary | None = Field(
        default=None,
        alias="latestResult",
        description="Summary of the latest result metadata, when available.",
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
        data.pop("__ade_run_options", None)
        return data

    @model_validator(mode="after")
    def _derive_defaults(self) -> DocumentOut:
        if self.activity_at is None:
            self.activity_at = self.updated_at
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
        alias="assigneeId",
        description="Assign the document to a user (null clears assignment).",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Replace the document metadata payload.",
    )

    @model_validator(mode="after")
    def _ensure_changes(self) -> DocumentUpdateRequest:
        assignee_set = "assignee_user_id" in self.model_fields_set
        if not assignee_set and self.metadata is None:
            raise ValueError("assigneeId or metadata is required")
        return self


class DocumentBatchTagsRequest(BaseSchema):
    """Payload for updating tags on multiple documents."""

    document_ids: list[UUIDStr] = Field(
        ...,
        min_length=1,
        alias="documentIds",
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
        alias="documentIds",
        description="Documents to delete (soft delete, all-or-nothing).",
    )


class DocumentBatchDeleteResponse(BaseSchema):
    """Response envelope for batch deletions."""

    document_ids: list[UUIDStr] = Field(default_factory=list, alias="documentIds")


class DocumentBatchArchiveRequest(BaseSchema):
    """Payload for archiving or restoring multiple documents."""

    document_ids: list[UUIDStr] = Field(
        ...,
        min_length=1,
        alias="documentIds",
        description="Documents to archive or restore (all-or-nothing).",
    )


class DocumentBatchArchiveResponse(BaseSchema):
    """Response envelope for batch archive or restore operations."""

    documents: list[DocumentOut] = Field(default_factory=list)


class TagCatalogItem(BaseSchema):
    """Tag entry with document counts."""

    tag: str
    document_count: int = Field(ge=0)


class TagCatalogPage(ListPage[TagCatalogItem]):
    """Paginated tag catalog."""


class DocumentRunSummary(BaseSchema):
    """Minimal representation of a run associated with a document."""

    id: UUIDStr = Field(description="Run identifier.")
    status: RunStatus
    started_at: datetime | None = Field(
        default=None,
        alias="startedAt",
        description="Timestamp for when the run started, if available.",
    )
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="Timestamp for when the run completed, if available.",
    )
    error_summary: str | None = Field(
        default=None,
        alias="errorSummary",
        description="Optional error summary from the run.",
    )


class DocumentResultSummary(BaseSchema):
    """Summary of the latest document result metadata."""

    attention: int = Field(ge=0)
    unmapped: int = Field(ge=0)
    pending: bool | None = None


class DocumentListRow(BaseSchema):
    """Table-ready projection for document list rows."""

    id: UUIDStr = Field(description="Document UUIDv7 (RFC 9562).")
    workspace_id: UUIDStr = Field(alias="workspaceId")
    name: str = Field(description="Display name mapped from the original filename.")
    file_type: DocumentFileType = Field(alias="fileType")
    status: DocumentStatus
    uploader: UserSummary | None = None
    assignee: UserSummary | None = None
    tags: list[str] = Field(default_factory=list)
    byte_size: int = Field(alias="byteSize")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    activity_at: datetime = Field(alias="activityAt")
    latest_run: DocumentRunSummary | None = Field(default=None, alias="latestRun")
    latest_successful_run: DocumentRunSummary | None = Field(
        default=None,
        alias="latestSuccessfulRun",
    )
    latest_result: DocumentResultSummary | None = Field(default=None, alias="latestResult")


class DocumentListPage(ListPage[DocumentListRow]):
    """Paginated envelope of document list rows."""

    changes_cursor: str = Field(
        description="Watermark cursor for the documents change feed at response time.",
        alias="changesCursor",
    )


class DocumentChangeEntry(BaseSchema):
    """Single entry from the documents change feed."""

    cursor: str
    type: Literal["document.upsert", "document.deleted"]
    row: DocumentListRow | None = None
    document_id: UUIDStr | None = Field(default=None, alias="documentId")
    occurred_at: datetime = Field(alias="occurredAt")
    matches_filters: bool = Field(default=False, alias="matchesFilters")
    requires_refresh: bool = Field(default=False, alias="requiresRefresh")

    @model_validator(mode="after")
    def _validate_payload(self) -> DocumentChangeEntry:
        if self.type == "document.deleted" and not self.document_id:
            raise ValueError("document_id is required for document.deleted changes")
        if self.type == "document.upsert" and self.row is None:
            raise ValueError("row is required for document.upsert changes")
        return self


class DocumentChangesPage(BaseSchema):
    """Envelope for cursor-based change feed results."""

    items: list[DocumentChangeEntry] = Field(default_factory=list)
    next_cursor: str = Field(alias="nextCursor")


class DocumentUploadRunOptions(BaseSchema):
    """Run-specific options captured at upload time."""

    input_sheet_names: list[str] | None = Field(
        default=None,
        alias="inputSheetNames",
        description="Optional worksheet names to ingest when processing XLSX files.",
    )
    active_sheet_only: bool = Field(
        default=False,
        alias="activeSheetOnly",
        description="If true, process only the active worksheet when ingesting XLSX files.",
    )

    @model_validator(mode="after")
    def _validate_sheet_options(self) -> DocumentUploadRunOptions:
        if self.active_sheet_only and self.input_sheet_names:
            raise ValueError("active_sheet_only cannot be combined with input_sheet_names")
        return self


class DocumentUploadSessionCreateRequest(BaseSchema):
    """Create a resumable upload session for a document."""

    filename: str
    byte_size: int = Field(ge=1, alias="byteSize")
    content_type: str | None = Field(default=None, alias="contentType")
    conflict_behavior: DocumentUploadConflictBehavior = Field(
        default=DocumentUploadConflictBehavior.RENAME,
        alias="conflictBehavior",
    )
    folder_id: str | None = Field(default=None, alias="folderId")
    metadata: dict[str, Any] | None = None
    run_options: DocumentUploadRunOptions | None = Field(default=None, alias="runOptions")


class DocumentUploadSessionCreateResponse(BaseSchema):
    """Response payload for a new upload session."""

    upload_session_id: UUIDStr = Field(alias="uploadSessionId")
    expires_at: datetime = Field(alias="expiresAt")
    chunk_size_bytes: int = Field(alias="chunkSizeBytes")
    next_expected_ranges: list[str] = Field(alias="nextExpectedRanges")
    upload_url: str = Field(alias="uploadUrl")


class DocumentUploadSessionStatusResponse(BaseSchema):
    """Status payload for an upload session."""

    upload_session_id: UUIDStr = Field(alias="uploadSessionId")
    expires_at: datetime = Field(alias="expiresAt")
    byte_size: int = Field(alias="byteSize")
    received_bytes: int = Field(alias="receivedBytes")
    next_expected_ranges: list[str] = Field(alias="nextExpectedRanges")
    upload_complete: bool = Field(default=False, alias="uploadComplete")
    status: DocumentUploadSessionStatus


class DocumentUploadSessionUploadResponse(BaseSchema):
    """Response payload after uploading a range."""

    next_expected_ranges: list[str] = Field(alias="nextExpectedRanges")
    upload_complete: bool = Field(default=False, alias="uploadComplete")


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
    "DocumentFileType",
    "DocumentListPage",
    "DocumentListRow",
    "DocumentOut",
    "DocumentResultSummary",
    "DocumentRunSummary",
    "DocumentSheet",
    "DocumentTagsPatch",
    "DocumentTagsReplace",
    "DocumentUpdateRequest",
    "DocumentUploadRunOptions",
    "DocumentUploadSessionCreateRequest",
    "DocumentUploadSessionCreateResponse",
    "DocumentUploadSessionStatusResponse",
    "DocumentUploadSessionUploadResponse",
    "TagCatalogItem",
    "TagCatalogPage",
    "UserSummary",
]
