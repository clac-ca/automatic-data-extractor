"""SQLAlchemy models for configuration metadata."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..workspaces.models import Workspace


class Configuration(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned configuration payloads for document processing."""

    __tablename__ = "configurations"
    __ulid_field__ = "configuration_id"

    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="joined")

    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "document_type", "version"),
        Index(
            "configurations_workspace_active_idx",
            "workspace_id",
            "document_type",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )


__all__ = ["Configuration"]
