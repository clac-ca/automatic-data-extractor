"""Database models for workspace configurations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ade_db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class ConfigurationStatus(str, Enum):
    """Lifecycle states for workspace configuration packages."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ConfigurationSourceKind(str, Enum):
    """Provenance marker for how a configuration was created."""

    TEMPLATE = "template"
    IMPORT = "import"
    CLONE = "clone"
    RESTORE = "restore"


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
    source_configuration_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("configurations.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_kind: Mapped[ConfigurationSourceKind] = mapped_column(
        SAEnum(
            ConfigurationSourceKind,
            name="configuration_source_kind",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ConfigurationSourceKind.TEMPLATE,
        server_default=ConfigurationSourceKind.TEMPLATE.value,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_configurations_workspace_status", "workspace_id", "status"),
        Index("ix_configurations_workspace_source", "workspace_id", "source_configuration_id"),
    )


__all__ = ["Configuration", "ConfigurationStatus", "ConfigurationSourceKind"]
