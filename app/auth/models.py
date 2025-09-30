from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin, ULIDPrimaryKeyMixin
from ..users.models import User


class APIKey(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored representation of an issued API key secret."""

    __tablename__ = "api_keys"
    __ulid_field__ = "api_key_id"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_seen_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_seen_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_seen_user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User | None] = relationship(User, lazy="joined")


__all__ = ["APIKey"]
