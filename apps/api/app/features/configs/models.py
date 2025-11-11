"""Database models for workspace configurations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.shared.db import Base
from apps.api.app.shared.db.mixins import TimestampMixin, generate_ulid


class ConfigurationStatus(str, Enum):
    """Lifecycle states for workspace configuration packages."""

    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class Configuration(TimestampMixin, Base):
    """Workspace-owned configuration package metadata."""

    __tablename__ = "configurations"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        primary_key=True,
    )
    config_id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        default=generate_ulid,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ConfigurationStatus] = mapped_column(
        SAEnum(
            ConfigurationStatus,
            name="configuration_status",
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=ConfigurationStatus.DRAFT,
    )
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("configurations_workspace_status_idx", "workspace_id", "status"),
    )


__all__ = ["Configuration", "ConfigurationStatus"]
