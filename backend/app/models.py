"""Database models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import ulid
from sqlalchemy import Boolean, JSON, String
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_ulid() -> str:
    return str(ulid.new())


class Snapshot(Base):
    """Snapshot metadata and payloads."""

    __tablename__ = "snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=_generate_ulid)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Persist arbitrary structured data. Callers should reassign ``payload``
    # instead of mutating nested keys so change tracking stays predictable.
    payload: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    created_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=_timestamp, onupdate=_timestamp, nullable=False)

    def __repr__(self) -> str:
        return f"Snapshot(snapshot_id={self.snapshot_id!r}, document_type={self.document_type!r})"


__all__ = ["Snapshot"]
