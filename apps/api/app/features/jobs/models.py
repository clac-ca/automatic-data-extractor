"""SQLAlchemy models representing ADE jobs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.shared.db import Base, TimestampMixin, ULIDPrimaryKeyMixin
from apps.api.app.shared.db.enums import enum_values

__all__ = ["Job", "JobStatus"]


class JobStatus(str, Enum):
    """Lifecycle states for ADE jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persistent orchestration job triggered from the workspace UI."""

    __tablename__ = "jobs"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    config_id: Mapped[str] = mapped_column(String(26), nullable=False)
    config_version_id: Mapped[str] = mapped_column(String(26), nullable=False)
    submitted_by_user_id: Mapped[str | None] = mapped_column(String(26), nullable=True)

    status: Mapped[JobStatus] = mapped_column(
        SAEnum(
            JobStatus,
            name="jobstatus",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retry_of_job_id: Mapped[str | None] = mapped_column(String(26), nullable=True)

    input_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_documents: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logs_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    run_request_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("jobs_workspace_idx", "workspace_id", "created_at"),
        Index("jobs_config_version_idx", "config_version_id"),
        Index("jobs_input_idx", "workspace_id", "config_version_id", "input_hash"),
        Index("jobs_status_queued_idx", "status", "queued_at"),
        Index("jobs_retry_of_idx", "retry_of_job_id"),
    )
