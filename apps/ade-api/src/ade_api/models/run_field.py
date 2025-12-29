"""Database model for per-field run summaries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.db import Base, UUIDType


class RunField(Base):
    """Persist field-level mapping info for a run."""

    __tablename__ = "run_fields"

    run_id: Mapped[UUID] = mapped_column(
        UUIDType(), ForeignKey("runs.id", ondelete="NO ACTION"), primary_key=True
    )
    field: Mapped[str] = mapped_column(String(128), primary_key=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mapped: Mapped[bool] = mapped_column(Boolean, nullable=False)
    best_mapping_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurrences_tables: Mapped[int] = mapped_column(Integer, nullable=False)
    occurrences_columns: Mapped[int] = mapped_column(Integer, nullable=False)


__all__ = ["RunField"]
