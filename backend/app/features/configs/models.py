"""SQLAlchemy models for file-backed configuration engine v0.4."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.shared.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from ..users.models import User
    from ..workspaces.models import Workspace


class ConfigStatus(StrEnum):
    """Enumerated lifecycle states for a configuration bundle."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class Config(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace-scoped configuration metadata referencing filesystem bundles."""

    __tablename__ = "configs"
    __ulid_field__ = "config_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="configs",
        lazy="joined",
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ConfigStatus] = mapped_column(
        Enum(
            ConfigStatus,
            name="config_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default=ConfigStatus.INACTIVE,
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    files_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    package_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys="Config.created_by",
        lazy="joined",
    )

    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    activated_by: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    activator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys="Config.activated_by",
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_by: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    archiver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys="Config.archived_by",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','inactive','archived')",
            name="configs_status_ck",
        ),
        Index(
            "configs_active_unique_idx",
            "workspace_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )


__all__ = ["Config", "ConfigStatus"]
