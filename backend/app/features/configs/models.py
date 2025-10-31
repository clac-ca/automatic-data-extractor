"""SQLAlchemy models for config metadata and workspace activation state."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.features.users.models import User
from backend.app.features.workspaces.models import Workspace
from backend.app.shared.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

__all__ = ["Config", "ConfigVersion", "WorkspaceConfigState"]


class Config(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Metadata describing a config package within a workspace."""

    __tablename__ = "configs"
    __ulid_field__ = "config_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="selectin")

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[created_by_user_id],
    )

    updated_by_user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[updated_by_user_id],
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    deleted_by: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[deleted_by_user_id],
    )

    versions: Mapped[list["ConfigVersion"]] = relationship(
        "ConfigVersion",
        back_populates="config",
        cascade="all, delete-orphan",
        order_by="ConfigVersion.sequence",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="configs_workspace_slug_key"),
        Index("configs_workspace_idx", "workspace_id"),
        Index("configs_workspace_deleted_idx", "workspace_id", "deleted_at"),
    )


class ConfigVersion(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable snapshot of a config package."""

    __tablename__ = "config_versions"
    __ulid_field__ = "config_version_id"

    config_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("configs.config_id", ondelete="CASCADE"),
        nullable=False,
    )
    config: Mapped[Config] = relationship("Config", back_populates="versions", lazy="selectin")

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    package_path: Mapped[str] = mapped_column(String(512), nullable=False)
    config_script_api_version: Mapped[str] = mapped_column(String(10), nullable=False)

    created_by_user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[created_by_user_id],
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    deleted_by: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
        foreign_keys=[deleted_by_user_id],
    )

    __table_args__ = (
        UniqueConstraint("config_id", "sequence", name="config_versions_sequence_key"),
        Index("config_versions_config_idx", "config_id"),
        Index("config_versions_deleted_idx", "config_id", "deleted_at"),
    )


class WorkspaceConfigState(TimestampMixin, Base):
    """Tracks the active config version for a workspace."""

    __tablename__ = "workspace_config_states"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        primary_key=True,
    )
    config_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("configs.config_id", ondelete="SET NULL"),
        nullable=True,
    )
    config_version_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("config_versions.config_version_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    config: Mapped[Config | None] = relationship("Config", lazy="selectin")
    config_version: Mapped[ConfigVersion | None] = relationship("ConfigVersion", lazy="selectin")

    __table_args__ = (
        Index("workspace_config_states_workspace_idx", "workspace_id"),
    )
