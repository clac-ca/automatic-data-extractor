from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...db import Base
from ...db.mixins import TimestampMixin, ULIDPrimaryKeyMixin
from ..users.models import User
from ..service_accounts.models import ServiceAccount


class APIKey(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored representation of an issued API key secret."""

    __tablename__ = "api_keys"
    __ulid_field__ = "api_key_id"

    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=True,
    )
    service_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("service_accounts.service_account_id", ondelete="CASCADE"),
        nullable=True,
    )
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_seen_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_seen_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_seen_user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User | None] = relationship(User, lazy="joined")
    service_account: Mapped[ServiceAccount | None] = relationship(ServiceAccount, lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND service_account_id IS NULL)"
            " OR (user_id IS NULL AND service_account_id IS NOT NULL)",
            name="api_keys_principal_check",
        ),
    )


__all__ = ["APIKey"]
