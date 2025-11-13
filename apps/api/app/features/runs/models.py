"""Database models capturing ADE run executions and logs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.app.shared.db import Base
from apps.api.app.shared.db.enums import enum_values
from apps.api.app.shared.core.time import utc_now

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
    config_id: Mapped[str] = mapped_column(String(26), nullable=False)

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    logs: Mapped[list["RunLog"]] = relationship(
        "RunLog",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("runs_config_idx", "config_id"),
        Index("runs_workspace_idx", "workspace_id"),
        Index("runs_status_idx", "status"),
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

    __table_args__ = (Index("run_logs_run_id_idx", "run_id"), Index("run_logs_stream_idx", "stream"))
