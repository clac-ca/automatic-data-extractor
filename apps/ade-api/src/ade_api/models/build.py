"""Database models for ADE configuration builds and logs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.common.time import utc_now
from ade_api.db import GUID, Base, UTCDateTime, UUIDPrimaryKeyMixin


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class BuildStatus(str, Enum):
    """Lifecycle states for API-facing build resources."""

    QUEUED = "queued"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Build(UUIDPrimaryKeyMixin, Base):
    """Persist build executions surfaced via the API."""

    __tablename__ = "builds"
    __table_args__ = (
        UniqueConstraint("configuration_id", "fingerprint", name="ux_builds_config_fingerprint"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False
    )
    configuration_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("configurations.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
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
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=BuildStatus.QUEUED.value,
        index=True,
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "BuildStatus",
    "Build",
]
