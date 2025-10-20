"""Lightweight ORM models kept during the jobs module rewrite."""

from __future__ import annotations

from typing import cast

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..workspaces.models import Workspace


class Job(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Processing job metadata and configuration details."""

    __tablename__ = "jobs"
    __ulid_field__ = "job_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="joined")
    configuration_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("configurations.configuration_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    input_document_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("documents.document_id", ondelete="RESTRICT"), nullable=False
    )
    metrics: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    logs: Mapped[list[dict[str, object]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )

    __table_args__ = (
        Index("jobs_workspace_id_idx", "workspace_id"),
        Index("jobs_input_document_id_idx", "input_document_id"),
    )


    @property
    def job_id(self) -> str:
        return cast(str, self.id)


__all__ = ["Job"]
