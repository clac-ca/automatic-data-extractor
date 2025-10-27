"""SQLAlchemy models for configuration packages, versions, and files."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.shared.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..users.models import User
from ..workspaces.models import Workspace


class Config(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace-scoped configuration package."""

    __tablename__ = "configs"
    __ulid_field__ = "config_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="joined")

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    created_by: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    creator: Mapped[User | None] = relationship("User", lazy="joined")

    versions: Mapped[list["ConfigVersion"]] = relationship(
        "ConfigVersion",
        back_populates="config",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)


class ConfigVersion(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable snapshot of configuration files and manifest."""

    __tablename__ = "config_versions"
    __ulid_field__ = "config_version_id"

    config_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("configs.config_id", ondelete="CASCADE"),
        nullable=False,
    )
    config: Mapped[Config] = relationship("Config", back_populates="versions")

    semver: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    files_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    created_by: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    creator: Mapped[User | None] = relationship("User")

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    files: Mapped[list["ConfigFile"]] = relationship(
        "ConfigFile",
        back_populates="version",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("config_id", "semver"),
        CheckConstraint(
            "status IN ('draft','published','deprecated')",
            name="config_versions_status_ck",
        ),
        Index(
            "config_versions_draft_unique_idx",
            "config_id",
            unique=True,
            sqlite_where=text("status = 'draft'"),
            postgresql_where=text("status = 'draft'"),
        ),
        Index(
            "config_versions_published_unique_idx",
            "config_id",
            unique=True,
            sqlite_where=text("status = 'published'"),
            postgresql_where=text("status = 'published'"),
        ),
    )


class ConfigFile(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Code file associated with a configuration version."""

    __tablename__ = "config_files"
    __ulid_field__ = "config_file_id"

    config_version_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("config_versions.config_version_id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[ConfigVersion] = relationship("ConfigVersion", back_populates="files")

    path: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="python")
    code: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (UniqueConstraint("config_version_id", "path"),)


__all__ = ["Config", "ConfigVersion", "ConfigFile"]

