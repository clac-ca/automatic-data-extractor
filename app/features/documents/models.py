"""Lightweight ORM models kept during the documents module rewrite."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import DateTime, JSON, ForeignKey, Index, Integer, String
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..workspaces.models import Workspace


class Document(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Uploaded document metadata with deterministic storage paths."""

    __tablename__ = "documents"
    __ulid_field__ = "document_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="joined")

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stored_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    attributes: Mapped[dict[str, object]] = mapped_column(
        "attributes",
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    produced_by_job_id: Mapped[str | None] = mapped_column(String(26), nullable=True)

    __table_args__ = (
        Index("documents_workspace_id_idx", "workspace_id"),
        Index("documents_produced_by_job_id_idx", "produced_by_job_id"),
    )

    @property
    def document_id(self) -> str:
        """Expose a stable attribute for integrations expecting ``document_id``."""

        return cast(str, self.id)


__all__ = ["Document"]
