"""Database models for workspace configurations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.features.builds.models import BuildStatus
from ade_api.shared.db import Base
from ade_api.shared.db.enums import enum_values
from ade_api.shared.db.mixins import TimestampMixin, ULIDPrimaryKeyMixin


class ConfigurationStatus(str, Enum):
    """Lifecycle states for workspace configuration packages."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ACTIVE = "active"
    INACTIVE = "inactive"


class Configuration(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace-owned configuration package metadata."""

    __tablename__ = "configurations"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ConfigurationStatus] = mapped_column(
        SAEnum(
            ConfigurationStatus,
            name="configuration_status",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=ConfigurationStatus.DRAFT,
    )
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    build_status: Mapped[BuildStatus] = mapped_column(
        SAEnum(
            BuildStatus,
            name="configuration_build_status",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=BuildStatus.QUEUED,
    )
    engine_spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    python_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    python_interpreter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    built_configuration_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    built_content_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_build_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_build_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_build_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_build_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("configurations_workspace_status_idx", "workspace_id", "status"),
    )


__all__ = ["Configuration", "ConfigurationStatus"]
