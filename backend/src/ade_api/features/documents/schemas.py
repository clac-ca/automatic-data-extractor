"""Pydantic schemas for the documents module."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from ade_api.common.cursor_listing import CursorPage
from ade_api.common.ids import UUIDStr
from ade_api.common.schema import BaseSchema
from ade_api.features.runs.schemas import RunColumnResource, RunFieldResource, RunMetricsResource
from ade_db.models import FileVersionOrigin, RunStatus


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


class DocumentListLifecycle(str, Enum):
    """Visibility scope for list queries."""

    ACTIVE = "active"
    DELETED = "deleted"


class DocumentViewVisibility(str, Enum):
    """Visibility scope for saved document views."""

    SYSTEM = "system"
    PRIVATE = "private"
    PUBLIC = "public"


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
    """Payload for updating document name, metadata, or assignment."""

    name: str | None = Field(
        default=None,
        description="Rename the document within the workspace (extension changes are rejected).",
    )
    assignee_user_id: UUIDStr | None = Field(
        default=None,
        alias="assigneeId",
        description="Assign the document to a user (null clears assignment).",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Replace the document metadata payload.",
    )

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("name is required")
        return value

    @model_validator(mode="after")
    def _ensure_changes(self) -> DocumentUpdateRequest:
        name_set = "name" in self.model_fields_set
        assignee_set = "assignee_user_id" in self.model_fields_set
        if name_set and self.name is None:
            raise ValueError("name cannot be null")
        if not name_set and not assignee_set and self.metadata is None:
            raise ValueError("name, assigneeId, or metadata is required")
        return self


class DocumentRestoreRequest(BaseSchema):
    """Optional payload for restoring a document with a new name."""

    name: str | None = Field(
        default=None,
        description="Optional replacement name used while restoring a deleted document.",
    )

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("name is required")
        return value


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


class DocumentBatchRestoreRequest(BaseSchema):
    """Payload for restoring multiple soft-deleted documents."""

    document_ids: list[UUIDStr] = Field(
        ...,
        min_length=1,
        alias="documentIds",
        description="Documents to restore (each document resolved independently).",
    )


class DocumentBatchRestoreResponse(BaseSchema):
    """Response envelope for partial batch restore operations."""

    restored_ids: list[UUIDStr] = Field(default_factory=list, alias="restoredIds")
    conflicts: list[DocumentBatchRestoreConflict] = Field(default_factory=list)
    not_found_ids: list[UUIDStr] = Field(default_factory=list, alias="notFoundIds")


class DocumentBatchRestoreConflict(BaseSchema):
    """Conflict payload for a document that could not be restored."""

    document_id: UUIDStr = Field(alias="documentId")
    name: str
    conflicting_document_id: UUIDStr = Field(alias="conflictingDocumentId")
    conflicting_name: str = Field(alias="conflictingName")
    suggested_name: str = Field(alias="suggestedName")


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
    deleted_at: datetime | None = Field(default=None, alias="deletedAt")
    last_run: DocumentRunSummary | None = Field(default=None, alias="lastRun")
    last_run_metrics: RunMetricsResource | None = Field(default=None, alias="lastRunMetrics")
    last_run_table_columns: list[RunColumnResource] | None = Field(
        default=None,
        alias="lastRunTableColumns",
    )
    last_run_fields: list[RunFieldResource] | None = Field(default=None, alias="lastRunFields")


class DocumentListPage(CursorPage[DocumentListRow]):
    """Cursor-based envelope of document list rows."""


DocumentChangeOp = Literal["upsert", "delete"]


class DocumentChangeEntry(BaseSchema):
    """Single entry from the documents change feed."""

    id: str
    op: DocumentChangeOp
    document_id: UUIDStr = Field(alias="documentId")


class DocumentChangeDeltaResponse(BaseSchema):
    """Delta response for document changes."""

    changes: list[DocumentChangeEntry]
    next_since: str = Field(alias="nextSince")
    has_more: bool = Field(alias="hasMore")


class DocumentCommentMentionIn(BaseSchema):
    """Range-aware mention metadata for a draft comment."""

    user_id: UUIDStr = Field(alias="userId")
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def _validate_range(self) -> DocumentCommentMentionIn:
        if self.end <= self.start:
            raise ValueError("mention end must be greater than start")
        return self


DocumentActivityAnchorType = Literal["note", "document", "run"]


class DocumentActivityThreadCreate(BaseSchema):
    """Payload for creating a new document activity thread."""

    anchor_type: DocumentActivityAnchorType = Field(alias="anchorType")
    anchor_id: UUIDStr | None = Field(default=None, alias="anchorId")
    body: str = Field(min_length=1, max_length=4000)
    mentions: list[DocumentCommentMentionIn] | None = Field(
        default=None,
        description="Optional mention ranges within the comment body.",
    )

    @field_validator("body")
    @classmethod
    def _strip_body(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body is required")
        return stripped

    @model_validator(mode="after")
    def _validate_anchor(self) -> DocumentActivityThreadCreate:
        if self.anchor_type == "note":
            if self.anchor_id is not None:
                raise ValueError("note threads cannot specify an anchorId")
            return self
        if self.anchor_id is None:
            raise ValueError("anchorId is required for anchored threads")
        return self


class DocumentActivityCommentCreate(BaseSchema):
    """Payload for creating a comment in an existing document activity thread."""

    body: str = Field(min_length=1, max_length=4000)
    mentions: list[DocumentCommentMentionIn] | None = Field(
        default=None,
        description="Optional mention ranges within the comment body.",
    )

    @field_validator("body")
    @classmethod
    def _strip_body(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body is required")
        return stripped


class DocumentCommentUpdate(BaseSchema):
    """Payload for editing an existing document comment."""

    body: str = Field(min_length=1, max_length=4000)
    mentions: list[DocumentCommentMentionIn] | None = Field(
        default=None,
        description="Optional mention ranges within the edited comment body.",
    )

    @field_validator("body")
    @classmethod
    def _strip_body(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body is required")
        return stripped


class DocumentCommentMentionOut(BaseSchema):
    """Resolved mention payload for comment rendering."""

    user: UserSummary = Field(alias="mentioned_user", serialization_alias="user")
    start: int = Field(alias="start_index", serialization_alias="start")
    end: int = Field(alias="end_index", serialization_alias="end")


class DocumentCommentOut(BaseSchema):
    """Serialized representation of a document comment."""

    id: UUIDStr
    workspace_id: UUIDStr = Field(alias="workspaceId")
    document_id: UUIDStr = Field(alias="file_id", serialization_alias="documentId")
    thread_id: UUIDStr = Field(alias="threadId")
    body: str
    author: UserSummary | None = Field(
        default=None,
        alias="author_user",
        serialization_alias="author",
    )
    mentions: list[DocumentCommentMentionOut] = Field(
        default_factory=list,
        alias="mention_ranges",
        serialization_alias="mentions",
    )
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    edited_at: datetime | None = Field(default=None, alias="editedAt")

class DocumentActivityThreadOut(BaseSchema):
    """Serialized document activity thread."""

    id: UUIDStr
    workspace_id: UUIDStr = Field(alias="workspaceId")
    document_id: UUIDStr = Field(alias="file_id", serialization_alias="documentId")
    anchor_type: DocumentActivityAnchorType = Field(alias="anchorType")
    anchor_id: UUIDStr | None = Field(default=None, alias="anchorId")
    activity_at: datetime = Field(alias="activityAt")
    comments: list[DocumentCommentOut] = Field(default_factory=list)
    comment_count: int = Field(default=0, alias="commentCount")


class DocumentActivityRunOut(BaseSchema):
    """Run summary embedded in the document activity timeline."""

    id: UUIDStr
    operation: str
    status: RunStatus
    created_at: datetime = Field(alias="createdAt")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    duration_seconds: float | None = Field(default=None, alias="durationSeconds")
    exit_code: int | None = Field(default=None, alias="exitCode")
    error_message: str | None = Field(default=None, alias="errorMessage")


class DocumentActivityDocumentItemOut(BaseSchema):
    """Upload event inside the document activity timeline."""

    id: str
    type: Literal["document"] = "document"
    activity_at: datetime = Field(alias="activityAt")
    title: str = "Document uploaded"
    uploader: UserSummary | None = Field(
        default=None,
        alias="uploaded_by_user",
        serialization_alias="uploader",
    )
    thread: DocumentActivityThreadOut | None = None


class DocumentActivityRunItemOut(BaseSchema):
    """Run event inside the document activity timeline."""

    id: str
    type: Literal["run"] = "run"
    activity_at: datetime = Field(alias="activityAt")
    run: DocumentActivityRunOut
    thread: DocumentActivityThreadOut | None = None


class DocumentActivityNoteItemOut(BaseSchema):
    """Freeform note thread inside the document activity timeline."""

    id: str
    type: Literal["note"] = "note"
    activity_at: datetime = Field(alias="activityAt")
    thread: DocumentActivityThreadOut


DocumentActivityItemOut = Annotated[
    DocumentActivityDocumentItemOut | DocumentActivityRunItemOut | DocumentActivityNoteItemOut,
    Field(discriminator="type"),
]


class DocumentActivityResponse(BaseSchema):
    """Full document activity timeline."""

    items: list[DocumentActivityItemOut]


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


class DocumentViewQueryState(BaseSchema):
    """Serializable list query state persisted for a saved view."""

    lifecycle: DocumentListLifecycle = DocumentListLifecycle.ACTIVE
    q: str | None = None
    sort: list[dict[str, Any]] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    join_operator: Literal["and", "or"] | None = Field(default="and", alias="joinOperator")


class DocumentViewTableState(BaseSchema):
    """Serializable table layout state persisted for a saved view."""

    column_visibility: dict[str, bool] | None = Field(default=None, alias="columnVisibility")
    column_sizing: dict[str, int] | None = Field(default=None, alias="columnSizing")
    column_order: list[str] | None = Field(default=None, alias="columnOrder")
    column_pinning: dict[str, list[str]] | None = Field(default=None, alias="columnPinning")


class DocumentViewCreate(BaseSchema):
    """Payload for creating a saved document view."""

    name: str = Field(min_length=1, max_length=120)
    visibility: Literal["private", "public"] = "private"
    query_state: DocumentViewQueryState = Field(alias="queryState")
    table_state: DocumentViewTableState | None = Field(default=None, alias="tableState")

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name is required")
        return stripped


class DocumentViewUpdate(BaseSchema):
    """Payload for updating a saved document view."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    visibility: Literal["private", "public"] | None = None
    query_state: DocumentViewQueryState | None = Field(default=None, alias="queryState")
    table_state: DocumentViewTableState | None = Field(default=None, alias="tableState")

    @field_validator("name")
    @classmethod
    def _strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("name is required")
        return stripped

    @model_validator(mode="after")
    def _ensure_any_change(self) -> DocumentViewUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one field must be updated")
        return self


class DocumentViewOut(BaseSchema):
    """Saved document view resource."""

    id: UUIDStr
    workspace_id: UUIDStr = Field(alias="workspaceId")
    name: str
    visibility: DocumentViewVisibility
    system_key: str | None = Field(default=None, alias="systemKey")
    owner_user_id: UUIDStr | None = Field(default=None, alias="ownerUserId")
    query_state: DocumentViewQueryState = Field(alias="queryState")
    table_state: DocumentViewTableState | None = Field(default=None, alias="tableState")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class DocumentViewListResponse(BaseSchema):
    """Collection of visible document views."""

    items: list[DocumentViewOut]


class DocumentSheet(BaseSchema):
    """Descriptor for a worksheet or single-sheet document."""

    name: str
    index: int = Field(ge=0)
    kind: Literal["worksheet", "file"] = "worksheet"
    is_active: bool = False


__all__ = [
    "DocumentBatchDeleteRequest",
    "DocumentBatchDeleteResponse",
    "DocumentBatchRestoreConflict",
    "DocumentBatchRestoreRequest",
    "DocumentBatchRestoreResponse",
    "DocumentBatchTagsRequest",
    "DocumentBatchTagsResponse",
    "DocumentRestoreRequest",
    "DocumentListLifecycle",
    "DocumentConflictMode",
    "DocumentChangeDeltaResponse",
    "DocumentChangeEntry",
    "DocumentChangeOp",
    "DocumentFileType",
    "DocumentListPage",
    "DocumentListRow",
    "DocumentOut",
    "DocumentViewCreate",
    "DocumentViewListResponse",
    "DocumentViewOut",
    "DocumentViewQueryState",
    "DocumentViewTableState",
    "DocumentViewUpdate",
    "DocumentViewVisibility",
    "DocumentActivityAnchorType",
    "DocumentActivityCommentCreate",
    "DocumentActivityDocumentItemOut",
    "DocumentActivityItemOut",
    "DocumentActivityNoteItemOut",
    "DocumentActivityResponse",
    "DocumentActivityRunItemOut",
    "DocumentActivityRunOut",
    "DocumentActivityThreadCreate",
    "DocumentActivityThreadOut",
    "DocumentCommentMentionIn",
    "DocumentCommentMentionOut",
    "DocumentCommentOut",
    "DocumentCommentUpdate",
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
