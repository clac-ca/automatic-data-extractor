from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base
from ...db.mixins import TimestampMixin, ULIDPrimaryKeyMixin


class ExtractedTable(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured table output produced by the extraction pipeline."""

    __tablename__ = "extracted_tables"
    __ulid_field__ = "table_id"

    job_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    columns: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )
    sample_rows: Mapped[list[dict[str, object]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSON), default=dict, nullable=False
    )

    __table_args__ = (
        Index("extracted_tables_job_id_idx", "job_id"),
        Index("extracted_tables_document_id_idx", "document_id"),
    )


__all__ = ["ExtractedTable"]
