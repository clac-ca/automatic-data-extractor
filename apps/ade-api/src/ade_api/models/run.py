"""Database models capturing ADE run executions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.common.time import utc_now
from ade_api.db import GUID, Base, UTCDateTime, UUIDPrimaryKeyMixin


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class RunStatus(str, Enum):
    """Lifecycle states for ADE runs."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Run(UUIDPrimaryKeyMixin, Base):
    """Persistent record of an ADE engine execution."""

    __tablename__ = "runs"

    configuration_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("configurations.id", ondelete="NO ACTION"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="NO ACTION"), nullable=False
    )
    build_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("builds.id", ondelete="NO ACTION"), nullable=True
    )
    input_document_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="NO ACTION"), nullable=False
    )
    run_options: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    input_sheet_names: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    claimed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    status: Mapped[RunStatus] = mapped_column(
        SAEnum(
            RunStatus,
            name="run_status",
            native_enum=False,
            length=20,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=RunStatus.QUEUED,
        server_default=RunStatus.QUEUED.value,
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
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
        Index("ix_runs_claim", "status", "available_at", "created_at"),
        Index(
            "uq_runs_active_job",
            "workspace_id",
            "input_document_id",
            "configuration_id",
            unique=True,
            sqlite_where=text("status IN ('queued','running')"),
            mssql_where=text("status IN ('queued','running')"),
        ),
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
