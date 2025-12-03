"""ORM models for uploaded documents and tags."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.infra.db import Base, TimestampMixin, UUIDPrimaryKeyMixin, UUIDType
from ade_api.infra.db.enums import enum_values

from .user import User
from .workspace import Workspace


class DocumentStatus(str, Enum):
    """Canonical document processing states."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentSource(str, Enum):
    """Origins for uploaded documents."""

    MANUAL_UPLOAD = "manual_upload"


DOCUMENT_STATUS_VALUES = tuple(status.value for status in DocumentStatus)
DOCUMENT_SOURCE_VALUES = tuple(source.value for source in DocumentSource)


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Uploaded document metadata with deterministic storage paths."""

    __tablename__ = "documents"
    workspace_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="selectin")

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stored_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    attributes: Mapped[dict[str, object]] = mapped_column(
        "attributes",
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    uploaded_by_user: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[uploaded_by_user_id],
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(
            DocumentStatus,
            name="document_status",
            native_enum=False,
            length=20,
            values_callable=enum_values,
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
            values_callable=enum_values,
        ),
        nullable=False,
        default=DocumentSource.MANUAL_UPLOAD,
        server_default=DocumentSource.MANUAL_UPLOAD.value,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
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
            postgresql_where=text("deleted_at IS NULL"),
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
        Index(
            "ix_documents_workspace_uploader", "workspace_id", "uploaded_by_user_id"
        ),
    )

    @property
    def tag_values(self) -> list[str]:
        """Return the tag strings associated with the document."""

        return [entry.tag for entry in getattr(self, "tags", [])]


class DocumentTag(Base):
    """Join table capturing string tags applied to documents."""

    __tablename__ = "document_tags"

    document_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("documents.id", ondelete="NO ACTION"),
        primary_key=True,
    )
    tag: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)

    document: Mapped[Document] = relationship(
        "Document",
        back_populates="tags",
        lazy="selectin",
    )

    __table_args__ = (
        Index("document_tags_document_id_idx", "document_id"),
        Index("document_tags_tag_idx", "tag"),
    )


__all__ = [
    "DOCUMENT_SOURCE_VALUES",
    "DOCUMENT_STATUS_VALUES",
    "Document",
    "DocumentSource",
    "DocumentStatus",
    "DocumentTag",
]
