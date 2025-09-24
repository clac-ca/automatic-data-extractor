"""Lightweight ORM models kept during the jobs module rewrite."""

from __future__ import annotations

from sqlalchemy import JSON, Index, Integer, String
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base
from ...db.mixins import TimestampMixin


class Job(TimestampMixin, Base):
    """Processing job metadata and configuration details."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    configuration_id: Mapped[str] = mapped_column(String(26), nullable=False)
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    input_document_id: Mapped[str] = mapped_column(String(26), nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    logs: Mapped[list[dict[str, object]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )

    __table_args__ = (Index("jobs_input_document_id_idx", "input_document_id"),)


__all__ = ["Job"]
