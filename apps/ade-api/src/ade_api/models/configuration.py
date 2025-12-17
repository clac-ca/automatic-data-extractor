"""Database models for workspace configurations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.db import Base, TimestampMixin, UUIDPrimaryKeyMixin, UUIDType
from ade_api.db.enums import enum_values


class ConfigurationStatus(str, Enum):
    """Lifecycle states for workspace configuration packages."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Configuration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace-owned configuration package metadata."""

    __tablename__ = "configurations"

    workspace_id: Mapped[UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="NO ACTION"),
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
        server_default=ConfigurationStatus.DRAFT.value,
    )
    content_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    active_build_id: Mapped[UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("builds.id", ondelete="NO ACTION"),
        nullable=True,
    )
    active_build_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_configurations_workspace_status", "workspace_id", "status"),
        Index("ix_configurations_active_build_id", "active_build_id"),
    )


__all__ = ["Configuration", "ConfigurationStatus"]
