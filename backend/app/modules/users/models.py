"""Database models for user accounts."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Boolean, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates

from ...db import Base
from ...db.mixins import TimestampMixin, ULIDPrimaryKeyMixin


class UserRole(StrEnum):
    """Application-level roles available to ADE operators."""

    ADMIN = "admin"
    MEMBER = "member"


class User(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registered ADE operator with optional password-based login."""

    __tablename__ = "users"
    __ulid_field__ = "user_id"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_canonical: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", native_enum=False, length=20),
        nullable=False,
        default=UserRole.MEMBER,
    )
    sso_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sso_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("sso_provider", "sso_subject"),
    )

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Email must not be empty")
        self.email_canonical = cleaned.lower()
        return cleaned


__all__ = ["User", "UserRole"]
