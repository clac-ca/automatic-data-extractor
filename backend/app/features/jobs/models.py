"""SQLAlchemy models and enums for job execution."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from backend.app.features.configs.models import Config, ConfigVersion
from backend.app.features.users.models import User
from backend.app.features.workspaces.models import Workspace
from backend.app.shared.db import Base, TimestampMixin, ULIDPrimaryKeyMixin


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Job(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Job metadata linking workspace, config version, and artifacts."""

    __tablename__ = "jobs"
    __ulid_field__ = "job_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="selectin")

    config_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("configs.config_id", ondelete="SET NULL"),
        nullable=False,
    )
    config: Mapped[Config] = relationship("Config", lazy="selectin")

    config_version_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("config_versions.config_version_id", ondelete="SET NULL"),
        nullable=False,
    )
    config_version: Mapped[ConfigVersion] = relationship(
        "ConfigVersion", lazy="selectin"
    )

    submitted_by_user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_by: Mapped[User | None] = relationship(
        "User", lazy="selectin", foreign_keys=[submitted_by_user_id]
    )

    status: Mapped[str] = mapped_column(
        SQLEnum(JobStatus, name="jobstatus", native_enum=False, length=20),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retry_of_job_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    retry_of: Mapped[Job | None] = relationship(
        "Job",
        remote_side="Job.id",
        lazy="selectin",
        primaryjoin="Job.retry_of_job_id == foreign(Job.id)",
    )
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    input_documents: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    artifact_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logs_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    run_request_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("jobs_workspace_idx", "workspace_id", "created_at"),
        Index("jobs_config_version_idx", "config_version_id"),
        Index("jobs_input_idx", "workspace_id", "config_version_id", "input_hash"),
        Index(
            "jobs_input_unique_idx",
            "workspace_id",
            "config_version_id",
            "input_hash",
            unique=True,
            sqlite_where=text("retry_of_job_id IS NULL"),
            postgresql_where=text("retry_of_job_id IS NULL"),
        ),
        Index("jobs_status_queued_idx", "status", "queued_at"),
        Index("jobs_retry_of_idx", "retry_of_job_id"),
    )


__all__ = ["Job", "JobStatus"]
