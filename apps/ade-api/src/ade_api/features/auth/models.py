from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_api.shared.db import Base, TimestampMixin, ULIDPrimaryKeyMixin

from ..users.models import User


class APIKey(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored representation of an issued API key secret."""

    __tablename__ = "api_keys"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_seen_user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # We always eagerly join the user for admin-facing listing endpoints.
    user: Mapped[User | None] = relationship(User, lazy="joined")


__all__ = ["APIKey"]
