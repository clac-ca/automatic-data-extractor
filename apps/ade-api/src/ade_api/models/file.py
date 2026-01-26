"""ORM models for files and file versions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace
    from .run import Run


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class FileKind(str, Enum):
    """Kinds of files stored in ADE."""

    DOCUMENT = "document"
    OUTPUT = "output"
    RUN_LOG = "run_log"
    EXPORT = "export"


class FileVersionOrigin(str, Enum):
    """Origins for file versions."""

    UPLOADED = "uploaded"
    GENERATED = "generated"
    MANUAL = "manual"


FILE_KIND_VALUES = tuple(kind.value for kind in FileKind)
FILE_VERSION_ORIGIN_VALUES = tuple(origin.value for origin in FileVersionOrigin)


class File(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-visible file identity (documents, outputs, logs)."""

    __tablename__ = "files"

    workspace_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="selectin")

    kind: Mapped[FileKind] = mapped_column(
        SAEnum(
            FileKind,
            name="file_kind",
            native_enum=False,
            length=50,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=FileKind.DOCUMENT,
        server_default=FileKind.DOCUMENT.value,
    )

    doc_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_key: Mapped[str] = mapped_column(String(255), nullable=False)
    blob_name: Mapped[str] = mapped_column(String(512), nullable=False)
    current_version_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("file_versions.id", ondelete="SET NULL"), nullable=True
    )
    current_version: Mapped[FileVersion | None] = relationship(
        "FileVersion",
        foreign_keys=[current_version_id],
        post_update=True,
        lazy="selectin",
    )

    parent_file_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="NO ACTION"), nullable=True
    )

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

    attributes: Mapped[dict[str, object]] = mapped_column(
        "attributes",
        MutableDict.as_mutable(JSONB),
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

    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_run_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    deleted_by_user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )

    tags: Mapped[list[FileTag]] = relationship(
        "FileTag",
        back_populates="file",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    versions: Mapped[list[FileVersion]] = relationship(
        "FileVersion",
        back_populates="file",
        foreign_keys="FileVersion.file_id",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "doc_no", name="files_workspace_doc_no_key"),
        UniqueConstraint(
            "workspace_id",
            "kind",
            "name_key",
            name="files_workspace_kind_name_key",
        ),
        Index("ix_files_workspace_created", "workspace_id", "created_at"),
        Index("ix_files_workspace_last_run_id", "workspace_id", "last_run_id"),
        Index("ix_files_workspace_uploader", "workspace_id", "uploaded_by_user_id"),
        Index("ix_files_workspace_assignee", "workspace_id", "assignee_user_id"),
    )

    @property
    def tag_values(self) -> list[str]:
        """Return the tag strings associated with the file."""

        return [entry.tag for entry in getattr(self, "tags", [])]

    @property
    def current_version_no(self) -> int | None:
        version = getattr(self, "current_version", None)
        return version.version_no if version is not None else None

    @property
    def byte_size(self) -> int | None:
        version = getattr(self, "current_version", None)
        return version.byte_size if version is not None else None

    @property
    def content_type(self) -> str | None:
        version = getattr(self, "current_version", None)
        return version.content_type if version is not None else None

    @property
    def sha256(self) -> str | None:
        version = getattr(self, "current_version", None)
        return version.sha256 if version is not None else None

    @property
    def filename_at_upload(self) -> str | None:
        version = getattr(self, "current_version", None)
        return version.filename_at_upload if version is not None else None

    @property
    def source(self) -> FileVersionOrigin | None:
        version = getattr(self, "current_version", None)
        return version.origin if version is not None else None


class FileVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable snapshot of file bytes."""

    __tablename__ = "file_versions"

    file_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("files.id", ondelete="NO ACTION"),
        nullable=False,
    )
    file: Mapped[File] = relationship(
        "File",
        back_populates="versions",
        foreign_keys=[file_id],
        lazy="selectin",
    )

    version_no: Mapped[int] = mapped_column(Integer, nullable=False)

    origin: Mapped[FileVersionOrigin] = mapped_column(
        SAEnum(
            FileVersionOrigin,
            name="file_version_origin",
            native_enum=False,
            length=50,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=FileVersionOrigin.UPLOADED,
        server_default=FileVersionOrigin.UPLOADED.value,
    )

    run_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("runs.id", ondelete="NO ACTION"), nullable=True
    )

    created_by_user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    created_by_user: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[created_by_user_id],
    )

    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename_at_upload: Mapped[str] = mapped_column(String(255), nullable=False)
    blob_version_id: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("file_id", "version_no", name="file_versions_file_id_version_no_key"),
        Index("ix_file_versions_file_id_created", "file_id", "created_at"),
        Index("ix_file_versions_file_id_version", "file_id", "version_no"),
    )


class FileTag(UUIDPrimaryKeyMixin, Base):
    """Join table capturing string tags applied to files."""

    __tablename__ = "file_tags"

    file_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("files.id", ondelete="NO ACTION"),
        nullable=False,
    )
    tag: Mapped[str] = mapped_column(String(100), nullable=False)

    file: Mapped[File] = relationship(
        "File",
        back_populates="tags",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("file_id", "tag", name="file_tags_file_id_tag_key"),
        Index("ix_file_tags_file_id", "file_id"),
        Index("ix_file_tags_tag", "tag"),
        Index("file_tags_tag_file_id_idx", "tag", "file_id"),
    )


class FileComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Threaded comments attached to a file (documents only)."""

    __tablename__ = "file_comments"

    workspace_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
        nullable=False,
    )
    file_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("files.id", ondelete="NO ACTION"),
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
    file: Mapped[File] = relationship("File", lazy="selectin")
    mentions: Mapped[list[FileCommentMention]] = relationship(
        "FileCommentMention",
        back_populates="comment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_file_comments_file_created", "file_id", "created_at"),
        Index("ix_file_comments_workspace_created", "workspace_id", "created_at"),
    )

    @property
    def mentioned_users(self) -> list[User]:
        return [
            mention.mentioned_user
            for mention in getattr(self, "mentions", [])
            if mention.mentioned_user is not None
        ]


class FileCommentMention(UUIDPrimaryKeyMixin, Base):
    """Join table for comment mentions."""

    __tablename__ = "file_comment_mentions"

    comment_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("file_comments.id", ondelete="CASCADE"),
        nullable=False,
    )
    mentioned_user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )

    comment: Mapped[FileComment] = relationship(
        "FileComment",
        back_populates="mentions",
        lazy="selectin",
    )
    mentioned_user: Mapped[User] = relationship("User", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "comment_id",
            "mentioned_user_id",
            name="file_comment_mentions_comment_user_key",
        ),
        Index("ix_file_comment_mentions_comment", "comment_id"),
        Index("ix_file_comment_mentions_user", "mentioned_user_id"),
    )


__all__ = [
    "File",
    "FileVersion",
    "FileTag",
    "FileComment",
    "FileCommentMention",
    "FileKind",
    "FileVersionOrigin",
    "FILE_KIND_VALUES",
    "FILE_VERSION_ORIGIN_VALUES",
]
