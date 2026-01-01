"""Idempotency key persistence for POST replays."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.db import Base, TimestampMixin, UUIDPrimaryKeyMixin
from ade_api.db.types import UTCDateTime


class IdempotencyRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Record of an idempotent request/response pair."""

    __tablename__ = "idempotency_keys"

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(nullable=False)
    response_headers: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    response_body: Mapped[object | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        UniqueConstraint("idempotency_key", "scope_key", name="uq_idempotency_scope"),
        Index("ix_idempotency_expires_at", "expires_at"),
    )


__all__ = ["IdempotencyRecord"]
