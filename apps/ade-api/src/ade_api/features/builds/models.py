"""Database models for ADE configuration builds and logs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.shared.db import Base
from ade_api.shared.db.enums import enum_values

__all__ = [
    "BuildStatus",
    "Build",
    "BuildLog",
]


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

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    configuration_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[BuildStatus] = mapped_column(
        SAEnum(
            BuildStatus,
            name="api_build_status",
            native_enum=False,
            length=20,
            values_callable=enum_values,
        ),
        nullable=False,
        index=True,
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    logs: Mapped[list[BuildLog]] = relationship(
        "BuildLog",
        back_populates="build",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BuildLog(Base):
    """Log chunks captured during build execution."""

    __tablename__ = "build_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    build_id: Mapped[str] = mapped_column(
        String, ForeignKey("builds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    stream: Mapped[str] = mapped_column(String(20), nullable=False, default="stdout")
    message: Mapped[str] = mapped_column(Text, nullable=False)

    build: Mapped[Build] = relationship("Build", back_populates="logs")
