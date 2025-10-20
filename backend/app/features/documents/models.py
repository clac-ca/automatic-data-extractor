"""Lightweight ORM models kept during the documents module rewrite."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    text,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..workspaces.models import Workspace
from ..users.models import User
from .filtering import (
    DOCUMENT_SOURCE_VALUES,
    DOCUMENT_STATUS_VALUES,
    DocumentSource,
    DocumentStatus,
)


class Document(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Uploaded document metadata with deterministic storage paths."""

    __tablename__ = "documents"
    __ulid_field__ = "document_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
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
    uploaded_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by_user: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[uploaded_by_user_id],
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentStatus.UPLOADED.value,
        server_default=text("'uploaded'"),
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=DocumentSource.MANUAL_UPLOAD.value,
        server_default=text("'manual_upload'"),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    produced_by_job_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("jobs.job_id", ondelete="SET NULL"), nullable=True
    )
    tags: Mapped[list["DocumentTag"]] = relationship(
        "DocumentTag",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{value}'" for value in DOCUMENT_STATUS_VALUES) + ")",
            name="documents_status_ck",
        ),
        CheckConstraint(
            "source IN (" + ", ".join(f"'{value}'" for value in DOCUMENT_SOURCE_VALUES) + ")",
            name="documents_source_ck",
        ),
        Index(
            "documents_workspace_status_created_idx",
            "workspace_id",
            "status",
            "created_at",
        ),
        Index(
            "documents_workspace_created_idx",
            "workspace_id",
            "created_at",
        ),
        Index(
            "documents_workspace_last_run_idx",
            "workspace_id",
            "last_run_at",
        ),
        Index("documents_workspace_source_idx", "workspace_id", "source"),
        Index(
            "documents_workspace_uploader_idx", "workspace_id", "uploaded_by_user_id"
        ),
        Index("documents_produced_by_job_id_idx", "produced_by_job_id"),
    )

    @property
    def document_id(self) -> str:
        """Expose a stable attribute for integrations expecting ``document_id``."""

        return cast(str, self.id)

    @property
    def tag_values(self) -> list[str]:
        """Return the tag strings associated with the document."""

        return [entry.tag for entry in getattr(self, "tags", [])]


class DocumentTag(Base):
    """Join table capturing string tags applied to documents."""

    __tablename__ = "document_tags"

    document_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag: Mapped[str] = mapped_column(String(100), primary_key=True)

    document: Mapped[Document] = relationship(
        "Document",
        back_populates="tags",
        lazy="selectin",
    )

    __table_args__ = (
        Index("document_tags_document_id_idx", "document_id"),
        Index("document_tags_tag_idx", "tag"),
    )


__all__ = ["Document", "DocumentTag"]
