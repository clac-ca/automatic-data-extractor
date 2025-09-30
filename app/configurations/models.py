"""SQLAlchemy models for configuration metadata."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.mixins import TimestampMixin, ULIDPrimaryKeyMixin


class Configuration(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned configuration payloads for document processing."""

    __tablename__ = "configurations"
    __ulid_field__ = "configuration_id"

    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activated_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("document_type", "version"),
        Index(
            "configurations_document_type_active_idx",
            "document_type",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )


__all__ = ["Configuration"]
