"""Database model for configuration build metadata."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.shared.db import Base
from apps.api.app.shared.db.mixins import TimestampMixin
from apps.api.app.shared.db.enums import enum_values

__all__ = ["BuildStatus", "ConfigurationBuild"]


class BuildStatus(str, Enum):
    """Lifecycle states for configuration build records."""

    BUILDING = "building"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class ConfigurationBuild(TimestampMixin, Base):
    """Track virtual environment builds for workspace configurations."""

    __tablename__ = "configuration_builds"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    config_id: Mapped[str] = mapped_column(String(26), nullable=False)
    build_id: Mapped[str] = mapped_column(String(26), nullable=False)

    status: Mapped[BuildStatus] = mapped_column(
        SAEnum(
            BuildStatus,
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
        PrimaryKeyConstraint("workspace_id", "config_id", "build_id"),
        ForeignKeyConstraint(
            ["workspace_id", "config_id"],
            ["configurations.workspace_id", "configurations.config_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status in ('building','active','inactive','failed')",
            name="configuration_builds_status_check",
        ),
        Index(
            "configuration_builds_active_idx",
            "workspace_id",
            "config_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "configuration_builds_building_idx",
            "workspace_id",
            "config_id",
            unique=True,
            sqlite_where=text("status = 'building'"),
            postgresql_where=text("status = 'building'"),
        ),
    )

    @property
    def environment_ref(self) -> str:
        """Return a stable reference for clients to identify the build environment."""

        return f"{self.workspace_id}/{self.config_id}/{self.build_id}"
