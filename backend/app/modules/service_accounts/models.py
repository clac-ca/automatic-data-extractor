from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from ...db import Base
from ...db.mixins import TimestampMixin, ULIDPrimaryKeyMixin
from ..users.models import User


class ServiceAccount(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Automated actor that can hold API keys independent of human users."""

    __tablename__ = "service_accounts"
    __ulid_field__ = "service_account_id"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped[User | None] = relationship(User, lazy="joined")

    @validates("name", "display_name")
    def _ensure_non_empty(self, _key: str, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            msg = "Value must not be empty"
            raise ValueError(msg)
        return candidate


__all__ = ["ServiceAccount"]
