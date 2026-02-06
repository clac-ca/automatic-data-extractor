"""Database models for worker-owned environments."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ade_db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class EnvironmentStatus(str, Enum):
    """Lifecycle states for worker-owned environments."""

    QUEUED = "queued"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


class Environment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Reusable execution environment metadata (owned by the worker)."""

    __tablename__ = "environments"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "configuration_id",
            "engine_spec",
            "deps_digest",
            name="ux_environments_key",
        ),
        Index("ix_environments_workspace", "workspace_id"),
        Index("ix_environments_configuration", "configuration_id"),
        Index("ix_environments_claim", "status", "created_at"),
        Index("ix_environments_status_last_used", "status", "last_used_at"),
        Index("ix_environments_status_updated", "status", "updated_at"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False
    )
    configuration_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("configurations.id", ondelete="NO ACTION"), nullable=False
    )
    engine_spec: Mapped[str] = mapped_column(String(255), nullable=False)
    deps_digest: Mapped[str] = mapped_column(String(128), nullable=False)

    status: Mapped[EnvironmentStatus] = mapped_column(
        SAEnum(
            EnvironmentStatus,
            name="environment_status",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=EnvironmentStatus.QUEUED.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    python_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    python_interpreter: Mapped[str | None] = mapped_column(String(512), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(50), nullable=True)


__all__ = ["Environment", "EnvironmentStatus"]
