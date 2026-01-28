"""Pydantic schemas for the documents module."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ade_api.common.ids import UUIDStr
from ade_api.common.cursor_listing import CursorPage
from ade_api.common.schema import BaseSchema
from ade_api.features.runs.schemas import RunColumnResource, RunFieldResource, RunMetricsResource
from ade_api.models import FileVersionOrigin, RunStatus


class DocumentFileType(str, Enum):
    """Normalized file types for documents."""

    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    PDF = "pdf"
    UNKNOWN = "unknown"


class DocumentConflictMode(str, Enum):
    """Conflict handling for document uploads."""

    REJECT = "reject"
    UPLOAD_NEW_VERSION = "upload_new_version"
    KEEP_BOTH = "keep_both"


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
    doc_no: int | None = Field(
        default=None,
        alias="docNo",
        description="Numeric document reference within the workspace.",
    )
    name: str = Field(description="Display name for the document.")
    content_type: str | None = Field(default=None, alias="contentType")
    byte_size: int = Field(alias="byteSize")
    current_version_no: int | None = Field(
        default=None,
        alias="currentVersionNo",
        description="Current file version number for this document.",
    )
    comment_count: int = Field(default=0, alias="commentCount")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        alias="attributes",
        serialization_alias="metadata",
    )
    source: FileVersionOrigin | None = Field(default=None)
    expires_at: datetime = Field(alias="expiresAt")
    activity_at: datetime | None = Field(default=None, alias="activityAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    version: int = Field(description="Monotonic document version.")
    etag: str | None = Field(
        default=None,
        description="Weak ETag for optimistic concurrency checks.",
    )
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
    last_run: DocumentRunSummary | None = Field(
        default=None,
        alias="lastRun",
        description="Last run created for the document when available.",
    )
    last_run_metrics: RunMetricsResource | None = Field(
        default=None,
        alias="lastRunMetrics",
        description="Last run metrics summary when available.",
    )
    last_run_table_columns: list[RunColumnResource] | None = Field(
        default=None,
        alias="lastRunTableColumns",
        description="Last run table column details when available.",
    )
    last_run_fields: list[RunFieldResource] | None = Field(
        default=None,
        alias="lastRunFields",
        description="Last run field detection summaries when available.",
    )
    list_row: DocumentListRow | None = Field(
        default=None,
        alias="listRow",
        description="Optional list row projection for table updates.",
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


class TagCatalogItem(BaseSchema):
    """Tag entry with document counts."""

    tag: str
    document_count: int = Field(ge=0)


class TagCatalogPage(CursorPage[TagCatalogItem]):
    """Cursor-based tag catalog."""


class DocumentRunSummary(BaseSchema):
    """Minimal representation of the latest run row for a document."""

    id: UUIDStr = Field(description="Run identifier.")
    status: RunStatus
    created_at: datetime = Field(
        alias="createdAt",
        description="Timestamp for when the run was created.",
    )
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
    error_message: str | None = Field(
        default=None,
        alias="errorMessage",
        description="Optional error message from the run.",
    )


class DocumentListRow(BaseSchema):
    """Table-ready projection for document list rows."""

    id: UUIDStr = Field(description="Document UUIDv7 (RFC 9562).")
    workspace_id: UUIDStr = Field(alias="workspaceId")
    doc_no: int | None = Field(default=None, alias="docNo")
    name: str = Field(description="Display name mapped from the original filename.")
    file_type: DocumentFileType = Field(alias="fileType")
    uploader: UserSummary | None = None
    assignee: UserSummary | None = None
    tags: list[str] = Field(default_factory=list)
    byte_size: int = Field(alias="byteSize")
    current_version_no: int | None = Field(default=None, alias="currentVersionNo")
    comment_count: int = Field(default=0, alias="commentCount")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    activity_at: datetime = Field(alias="activityAt")
    version: int = Field(description="Monotonic document version.")
    etag: str | None = Field(
        default=None,
        description="Weak ETag for optimistic concurrency checks.",
    )
    last_run: DocumentRunSummary | None = Field(default=None, alias="lastRun")
    last_run_metrics: RunMetricsResource | None = Field(default=None, alias="lastRunMetrics")
    last_run_table_columns: list[RunColumnResource] | None = Field(
        default=None,
        alias="lastRunTableColumns",
    )
    last_run_fields: list[RunFieldResource] | None = Field(default=None, alias="lastRunFields")


class DocumentListPage(CursorPage[DocumentListRow]):
    """Cursor-based envelope of document list rows."""


class DocumentEventEntry(BaseSchema):
    """Single entry from the documents event stream."""

    cursor: str
    type: Literal["document.changed", "document.deleted"]
    document_id: UUIDStr = Field(alias="documentId")
    occurred_at: datetime = Field(alias="occurredAt")
    document_version: int = Field(alias="documentVersion")
    row: DocumentListRow | None = Field(
        default=None,
        description="Optional list row snapshot for changed documents.",
    )


class DocumentCommentCreate(BaseSchema):
    """Payload for creating a document comment."""

    body: str = Field(min_length=1, max_length=4000)
    mentions: list[UUIDStr] | None = Field(
        default=None,
        description="Optional list of mentioned user IDs.",
    )

    @field_validator("body")
    @classmethod
    def _strip_body(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body is required")
        return stripped


class DocumentCommentOut(BaseSchema):
    """Serialized representation of a document comment."""

    id: UUIDStr
    workspace_id: UUIDStr = Field(alias="workspaceId")
    document_id: UUIDStr = Field(alias="file_id", serialization_alias="documentId")
    body: str
    author: UserSummary | None = Field(
        default=None,
        alias="author_user",
        serialization_alias="author",
    )
    mentions: list[UserSummary] = Field(
        default_factory=list,
        alias="mentioned_users",
        serialization_alias="mentions",
    )
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class DocumentCommentPage(CursorPage[DocumentCommentOut]):
    """Cursor-based envelope of document comments."""


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
    "DocumentConflictMode",
    "DocumentEventEntry",
    "DocumentFileType",
    "DocumentListPage",
    "DocumentListRow",
    "DocumentOut",
    "DocumentCommentCreate",
    "DocumentCommentOut",
    "DocumentCommentPage",
    "DocumentRunSummary",
    "DocumentSheet",
    "DocumentTagsPatch",
    "DocumentTagsReplace",
    "DocumentUpdateRequest",
    "DocumentUploadRunOptions",
    "TagCatalogItem",
    "TagCatalogPage",
    "UserSummary",
]
