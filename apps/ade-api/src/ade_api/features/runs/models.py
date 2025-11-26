"""Database models capturing ADE run executions and logs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.shared.core.time import utc_now
from ade_api.shared.db import Base
from ade_api.shared.db.enums import enum_values

__all__ = ["Run", "RunLog", "RunStatus"]


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

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    configuration_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    configuration_version_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    build_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_document_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
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
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retry_of_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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

    logs: Mapped[list[RunLog]] = relationship(
        "RunLog",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("runs_configuration_idx", "configuration_id"),
        Index("runs_workspace_idx", "workspace_id"),
        Index("runs_status_idx", "status"),
        Index("runs_input_document_idx", "input_document_id"),
        Index("runs_configuration_version_idx", "configuration_version_id"),
        Index("runs_workspace_created_idx", "workspace_id", "created_at"),
        Index("runs_retry_of_idx", "retry_of_run_id"),
    )


class RunLog(Base):
    """Append-only log entries captured during ADE run execution."""

    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    stream: Mapped[str] = mapped_column(String(20), nullable=False, default="stdout")
    message: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[Run] = relationship("Run", back_populates="logs")

    __table_args__ = (
        Index("run_logs_run_id_idx", "run_id"),
        Index("run_logs_stream_idx", "stream"),
    )
