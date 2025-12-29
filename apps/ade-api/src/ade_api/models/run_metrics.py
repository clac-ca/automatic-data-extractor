"""Database model for summarized ADE run metrics."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.db import Base, UUIDType


class RunMetrics(Base):
    """Persist a normalized summary of engine.run.completed for a run."""

    __tablename__ = "run_metrics"

    run_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("runs.id", ondelete="NO ACTION"), primary_key=True
    )

    evaluation_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    evaluation_findings_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_findings_info: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_findings_warning: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_findings_error: Mapped[int | None] = mapped_column(Integer, nullable=True)

    validation_issues_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_issues_info: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_issues_warning: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_issues_error: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_max_severity: Mapped[str | None] = mapped_column(String(10), nullable=True)

    workbook_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sheet_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    row_count_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count_empty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    column_count_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count_empty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count_mapped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count_ambiguous: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count_unmapped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count_passthrough: Mapped[int | None] = mapped_column(Integer, nullable=True)

    field_count_expected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_count_mapped: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cell_count_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cell_count_non_empty: Mapped[int | None] = mapped_column(Integer, nullable=True)


__all__ = ["RunMetrics"]
