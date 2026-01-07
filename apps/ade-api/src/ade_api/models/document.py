"""ORM models for uploaded documents and tags."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]

from .user import User
from .workspace import Workspace


class DocumentStatus(str, Enum):
    """Canonical document processing states."""

    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentSource(str, Enum):
    """Origins for uploaded documents."""

    MANUAL_UPLOAD = "manual_upload"


class DocumentEventType(str, Enum):
    """Persistent change feed event types for documents."""

    CHANGED = "document.changed"
    DELETED = "document.deleted"


class DocumentUploadConflictBehavior(str, Enum):
    """Conflict handling modes for upload sessions."""

    RENAME = "rename"
    REPLACE = "replace"
    FAIL = "fail"


class DocumentUploadSessionStatus(str, Enum):
    """Lifecycle states for document upload sessions."""

    ACTIVE = "active"
    COMPLETE = "complete"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


DOCUMENT_STATUS_VALUES = tuple(status.value for status in DocumentStatus)
DOCUMENT_SOURCE_VALUES = tuple(source.value for source in DocumentSource)
DOCUMENT_EVENT_TYPE_VALUES = tuple(change.value for change in DocumentEventType)
DOCUMENT_UPLOAD_CONFLICT_VALUES = tuple(mode.value for mode in DocumentUploadConflictBehavior)
DOCUMENT_UPLOAD_SESSION_STATUS_VALUES = tuple(status.value for status in DocumentUploadSessionStatus)


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Uploaded document metadata with deterministic storage paths."""

    __tablename__ = "documents"
    workspace_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="selectin")

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stored_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    attributes: Mapped[dict[str, object]] = mapped_column(
        "attributes",
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    uploaded_by_user: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[uploaded_by_user_id],
    )
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    assignee_user: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[assignee_user_id],
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(
            DocumentStatus,
            name="document_status",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        server_default=DocumentStatus.UPLOADED.value,
    )
    source: Mapped[DocumentSource] = mapped_column(
        SAEnum(
            DocumentSource,
            name="document_source",
            native_enum=False,
            length=50,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=DocumentSource.MANUAL_UPLOAD,
        server_default=DocumentSource.MANUAL_UPLOAD.value,
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    deleted_by_user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    tags: Mapped[list[DocumentTag]] = relationship(
        "DocumentTag",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_documents_workspace_status_created",
            "workspace_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_documents_workspace_status_created_live",
            "workspace_id",
            "status",
            "created_at",
            sqlite_where=text("deleted_at IS NULL"),
            mssql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_documents_workspace_created",
            "workspace_id",
            "created_at",
        ),
        Index(
            "ix_documents_workspace_last_run",
            "workspace_id",
            "last_run_at",
        ),
        Index("ix_documents_workspace_source", "workspace_id", "source"),
        Index("ix_documents_workspace_uploader", "workspace_id", "uploaded_by_user_id"),
        Index("ix_documents_workspace_assignee", "workspace_id", "assignee_user_id"),
    )

    @property
    def tag_values(self) -> list[str]:
        """Return the tag strings associated with the document."""

        return [entry.tag for entry in getattr(self, "tags", [])]


class DocumentTag(UUIDPrimaryKeyMixin, Base):
    """Join table capturing string tags applied to documents."""

    __tablename__ = "document_tags"

    document_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("documents.id", ondelete="NO ACTION"),
        nullable=False,
    )
    tag: Mapped[str] = mapped_column(String(100), nullable=False)

    document: Mapped[Document] = relationship(
        "Document",
        back_populates="tags",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("document_id", "tag", name="document_tags_document_id_tag_key"),
        Index("ix_document_tags_document_id", "document_id"),
        Index("ix_document_tags_tag", "tag"),
        Index("document_tags_tag_document_id_idx", "tag", "document_id"),
    )


class DocumentEvent(Base):
    """Durable change feed entry for documents."""

    __tablename__ = "document_events"

    cursor: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("documents.id", ondelete="NO ACTION"),
        nullable=False,
    )
    event_type: Mapped[DocumentEventType] = mapped_column(
        SAEnum(
            DocumentEventType,
            name="document_event_type",
            native_enum=False,
            length=40,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    client_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        Index("ix_document_events_workspace_cursor", "workspace_id", "cursor"),
        Index("ix_document_events_workspace_document", "workspace_id", "document_id"),
        Index("ix_document_events_workspace_occurred", "workspace_id", "occurred_at"),
    )


class DocumentUploadSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Resumable upload session metadata for large document uploads."""

    __tablename__ = "document_upload_sessions"

    workspace_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=True,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("documents.id", ondelete="NO ACTION"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # "metadata" is reserved by SQLAlchemy declarative base.
    upload_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    conflict_behavior: Mapped[DocumentUploadConflictBehavior] = mapped_column(
        SAEnum(
            DocumentUploadConflictBehavior,
            name="document_upload_conflict_behavior",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=DocumentUploadConflictBehavior.RENAME,
        server_default=DocumentUploadConflictBehavior.RENAME.value,
    )
    folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temp_stored_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    received_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    received_ranges: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    status: Mapped[DocumentUploadSessionStatus] = mapped_column(
        SAEnum(
            DocumentUploadSessionStatus,
            name="document_upload_session_status",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=DocumentUploadSessionStatus.ACTIVE,
        server_default=DocumentUploadSessionStatus.ACTIVE.value,
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        Index("ix_document_upload_sessions_workspace", "workspace_id"),
        Index("ix_document_upload_sessions_expires", "expires_at"),
        Index("ix_document_upload_sessions_status", "status"),
        Index("ix_document_upload_sessions_document", "document_id"),
    )


__all__ = [
    "DOCUMENT_EVENT_TYPE_VALUES",
    "DOCUMENT_SOURCE_VALUES",
    "DOCUMENT_STATUS_VALUES",
    "DOCUMENT_UPLOAD_CONFLICT_VALUES",
    "DOCUMENT_UPLOAD_SESSION_STATUS_VALUES",
    "DocumentEvent",
    "DocumentEventType",
    "Document",
    "DocumentSource",
    "DocumentStatus",
    "DocumentTag",
    "DocumentUploadConflictBehavior",
    "DocumentUploadSession",
    "DocumentUploadSessionStatus",
]
