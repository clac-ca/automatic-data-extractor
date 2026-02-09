"""Database models for workspace configurations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class ConfigurationStatus(str, Enum):
    """Lifecycle states for workspace configuration packages."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Configuration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace-owned configuration package metadata."""

    __tablename__ = "configurations"

    workspace_id: Mapped[UUID] = mapped_column(
        GUID(),
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
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ConfigurationStatus.DRAFT,
        server_default=ConfigurationStatus.DRAFT.value,
    )
    content_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_configurations_workspace_status", "workspace_id", "status"),
    )


__all__ = ["Configuration", "ConfigurationStatus"]
