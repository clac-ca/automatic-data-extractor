"""Lightweight ORM models kept during the documents module rewrite."""

from __future__ import annotations

from typing import cast

from sqlalchemy import JSON, Index, Integer, String
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.mixins import TimestampMixin, ULIDPrimaryKeyMixin


class Document(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Uploaded document metadata with deterministic storage paths."""

    __tablename__ = "documents"
    __ulid_field__ = "document_id"

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stored_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    produced_by_job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    __table_args__ = (
        Index("documents_produced_by_job_id_idx", "produced_by_job_id"),
    )

    @property
    def document_id(self) -> str:
        """Expose a stable attribute for integrations expecting ``document_id``."""

        return cast(str, self.id)


__all__ = ["Document"]
