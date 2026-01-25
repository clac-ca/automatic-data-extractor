"""ORM models for uploaded documents and tags."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class DocumentSource(str, Enum):
    """Origins for uploaded documents."""

    MANUAL_UPLOAD = "manual_upload"


class DocumentEventType(str, Enum):
    """Persistent change feed event types for documents."""

    CHANGED = "document.changed"
    DELETED = "document.deleted"


DOCUMENT_SOURCE_VALUES = tuple(source.value for source in DocumentSource)
DOCUMENT_EVENT_TYPE_VALUES = tuple(change.value for change in DocumentEventType)


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
    comment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
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
    last_run_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True)
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
            "ix_documents_workspace_created",
            "workspace_id",
            "created_at",
        ),
        Index(
            "ix_documents_workspace_last_run_id",
            "workspace_id",
            "last_run_id",
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


class DocumentComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Threaded comments attached to a document."""

    __tablename__ = "document_comments"

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
    author_user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    author_user: Mapped[User] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[author_user_id],
    )
    document: Mapped[Document] = relationship("Document", lazy="selectin")
    mentions: Mapped[list[DocumentCommentMention]] = relationship(
        "DocumentCommentMention",
        back_populates="comment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_document_comments_document_created", "document_id", "created_at"),
        Index("ix_document_comments_workspace_created", "workspace_id", "created_at"),
    )

    @property
    def mentioned_users(self) -> list[User]:
        return [
            mention.mentioned_user
            for mention in getattr(self, "mentions", [])
            if mention.mentioned_user is not None
        ]


class DocumentCommentMention(UUIDPrimaryKeyMixin, Base):
    """Join table for comment mentions."""

    __tablename__ = "document_comment_mentions"

    comment_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("document_comments.id", ondelete="CASCADE"),
        nullable=False,
    )
    mentioned_user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )

    comment: Mapped[DocumentComment] = relationship(
        "DocumentComment",
        back_populates="mentions",
        lazy="selectin",
    )
    mentioned_user: Mapped[User] = relationship("User", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "comment_id",
            "mentioned_user_id",
            name="document_comment_mentions_comment_user_key",
        ),
        Index("ix_document_comment_mentions_comment", "comment_id"),
        Index("ix_document_comment_mentions_user", "mentioned_user_id"),
    )


class DocumentEvent(Base):
    """Durable change feed entry for documents."""

    __tablename__ = "document_events"

    cursor: Mapped[int] = mapped_column(
        BigInteger(),
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
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        Index("ix_document_events_workspace_cursor", "workspace_id", "cursor"),
        Index("ix_document_events_workspace_document", "workspace_id", "document_id"),
        Index("ix_document_events_workspace_occurred", "workspace_id", "occurred_at"),
    )


__all__ = [
    "DOCUMENT_EVENT_TYPE_VALUES",
    "DOCUMENT_SOURCE_VALUES",
    "DocumentEvent",
    "DocumentEventType",
    "Document",
    "DocumentSource",
    "DocumentTag",
]
