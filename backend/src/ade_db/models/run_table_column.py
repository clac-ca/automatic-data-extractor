"""Database model for per-table detected columns."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ade_db import GUID, Base


class RunTableColumn(Base):
    """Persist detected columns and mappings for a run table."""

    __tablename__ = "run_table_columns"

    run_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("runs.id", ondelete="NO ACTION"), primary_key=True
    )
    workbook_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    workbook_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    column_index: Mapped[int] = mapped_column(Integer, primary_key=True)

    header_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    non_empty_cells: Mapped[int] = mapped_column(Integer, nullable=False)

    mapping_status: Mapped[str] = mapped_column(String(32), nullable=False)
    mapped_field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mapping_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    mapping_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unmapped_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)


__all__ = ["RunTableColumn"]
