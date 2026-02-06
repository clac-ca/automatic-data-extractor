"""API key model aligned with the current schema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin

from .user import User


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored representation of an issued API key."""

    __tablename__ = "api_keys"

    user_id: Mapped[UUID] = mapped_column(
        "user_id",
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    hashed_secret: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User | None] = relationship(
        User,
        foreign_keys=[user_id],
        lazy="joined",
    )

    __table_args__ = (
        Index(
            "ix_api_keys_user_id",
            "user_id",
        ),
    )


__all__ = ["ApiKey"]
