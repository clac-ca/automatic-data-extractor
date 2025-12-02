"""Database models for ADE configuration builds and logs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.infra.db import Base, UUIDType
from ade_api.infra.db.enums import enum_values


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
    __table_args__ = (
        Index(
            "ux_builds_inflight_per_config",
            "configuration_id",
            unique=True,
            postgresql_where=text("status in ('queued','building')"),
            sqlite_where=text("status in ('queued','building')"),
            mssql_where=text("status in ('queued','building')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=generate_uuid7)
    workspace_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    configuration_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    engine_spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    python_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    python_interpreter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)

    status: Mapped[BuildStatus] = mapped_column(
        SAEnum(
            BuildStatus,
            name="build_status",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        server_default=BuildStatus.QUEUED.value,
        index=True,
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "BuildStatus",
    "Build",
]
