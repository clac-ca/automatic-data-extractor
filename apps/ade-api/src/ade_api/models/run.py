"""Database models capturing ADE run executions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.db import Base, UUIDType
from ade_api.db.enums import enum_values
from ade_api.db.types import UTCDateTime


class RunStatus(str, Enum):
    """Lifecycle states for ADE runs."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Run(Base):
    """Persistent record of an ADE engine execution."""

    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=generate_uuid7)
    configuration_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("configurations.id", ondelete="NO ACTION"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False
    )
    build_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("builds.id", ondelete="NO ACTION"), nullable=False
    )
    input_document_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("documents.id", ondelete="NO ACTION"), nullable=False
    )
    input_sheet_names: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[RunStatus] = mapped_column(
        SAEnum(
            RunStatus,
            name="run_status",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=RunStatus.QUEUED,
        server_default=RunStatus.QUEUED.value,
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_runs_configuration", "configuration_id"),
        Index("ix_runs_workspace", "workspace_id"),
        Index("ix_runs_status", "status"),
        Index("ix_runs_input_document", "input_document_id"),
        Index(
            "ix_runs_workspace_input_finished",
            "workspace_id",
            "input_document_id",
            "completed_at",
            "started_at",
        ),
        Index("ix_runs_workspace_created", "workspace_id", "created_at"),
        Index("ix_runs_build", "build_id"),
    )


__all__ = ["Run", "RunStatus"]
