"""Database models for ADE configuration builds and logs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.app.shared.db import Base
from apps.api.app.shared.db.enums import enum_values
from apps.api.app.shared.db.mixins import TimestampMixin, ULIDPrimaryKeyMixin

__all__ = [
    "BuildStatus",
    "Build",
    "BuildLog",
    "ConfigurationBuildStatus",
    "ConfigurationBuild",
]


class BuildStatus(str, Enum):
    """Lifecycle states for API-facing build resources."""

    QUEUED = "queued"
    BUILDING = "building"
    ACTIVE = "active"
    FAILED = "failed"
    CANCELED = "canceled"


class Build(Base):
    """Persist build executions surfaced via the API."""

    __tablename__ = "builds"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    config_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    configuration_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False
    )
    configuration_build_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("configuration_builds.id", ondelete="SET NULL"), nullable=True
    )
    build_ref: Mapped[str | None] = mapped_column(
        String(26), nullable=True, index=True, doc="configuration_builds.build_id reference"
    )

    status: Mapped[BuildStatus] = mapped_column(
        SAEnum(
            BuildStatus,
            name="api_build_status",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        index=True,
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    logs: Mapped[list["BuildLog"]] = relationship(
        "BuildLog",
        back_populates="build",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BuildLog(Base):
    """Log chunks captured during build execution."""

    __tablename__ = "build_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    build_id: Mapped[str] = mapped_column(
        String, ForeignKey("builds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    stream: Mapped[str] = mapped_column(String(20), nullable=False, default="stdout")
    message: Mapped[str] = mapped_column(Text, nullable=False)

    build: Mapped[Build] = relationship("Build", back_populates="logs")


class ConfigurationBuildStatus(str, Enum):
    """Lifecycle states for configuration build pointer rows."""

    BUILDING = "building"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class ConfigurationBuild(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Track virtual environment builds for workspace configurations."""

    __tablename__ = "configuration_builds"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    config_id: Mapped[str] = mapped_column(String(26), nullable=False)
    configuration_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False
    )
    build_id: Mapped[str] = mapped_column(String(26), nullable=False)

    status: Mapped[ConfigurationBuildStatus] = mapped_column(
        SAEnum(
            ConfigurationBuildStatus,
            name="build_status",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    venv_path: Mapped[str] = mapped_column(Text, nullable=False)

    config_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    engine_spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    python_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    python_interpreter: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "config_id", "build_id"),
        CheckConstraint(
            "status in ('building','active','inactive','failed')",
            name="configuration_builds_status_check",
        ),
        Index(
            "configuration_builds_active_idx",
            "configuration_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "configuration_builds_building_idx",
            "configuration_id",
            unique=True,
            sqlite_where=text("status = 'building'"),
            postgresql_where=text("status = 'building'"),
        ),
    )

    @property
    def environment_ref(self) -> str:
        """Return a stable reference for clients to identify the build environment."""

        return f"{self.workspace_id}/{self.config_id}/{self.build_id}"

