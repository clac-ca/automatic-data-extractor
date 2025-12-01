"""Database models capturing ADE run executions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.shared.core.time import utc_now
from ade_api.shared.core.ids import generate_uuid7
from ade_api.shared.db import Base, UUIDType
from ade_api.shared.db.enums import enum_values

__all__ = ["Run", "RunStatus"]


class RunStatus(str, Enum):
    """Lifecycle states for ADE runs."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class Run(Base):
    """Persistent record of an ADE engine execution."""

    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(UUIDType(), primary_key=True, default=generate_uuid7)
    configuration_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    build_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("builds.id", ondelete="SET NULL"), nullable=True
    )
    input_document_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    input_documents: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    input_sheet_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    attempt: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    retry_of_run_id: Mapped[UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(
        UUIDType(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    artifact_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logs_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
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
            "finished_at",
            "started_at",
        ),
        Index("ix_runs_workspace_created", "workspace_id", "created_at"),
        Index("ix_runs_retry_of", "retry_of_run_id"),
        Index("ix_runs_build", "build_id"),
    )
