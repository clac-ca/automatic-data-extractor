"""SQLAlchemy models for ADE user identities."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates

from ...db import Base
from ...db.mixins import TimestampMixin, ULIDPrimaryKeyMixin


def _normalise_email(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        msg = "Email must not be empty"
        raise ValueError(msg)
    return cleaned


def _canonicalise_email(value: str) -> str:
    return value.lower()


def _clean_text(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        return cleaned[:max_length]
    return cleaned


class UserRole(StrEnum):
    """Supported ADE operator roles."""

    ADMIN = "admin"
    MEMBER = "member"


class User(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single identity model for humans and service accounts."""

    __tablename__ = "users"
    __ulid_field__ = "user_id"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_canonical: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_service_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", native_enum=False, length=20),
        nullable=False,
        default=UserRole.MEMBER,
    )
    sso_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sso_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("sso_provider", "sso_subject"),
    )

    @validates("email")
    def _store_normalised_email(self, _key: str, value: str) -> str:
        cleaned = _normalise_email(value)
        self.email_canonical = _canonicalise_email(cleaned)
        return cleaned

    @validates("display_name", "description")
    def _trim_text(self, key: str, value: str | None) -> str | None:  # noqa: ARG002
        limit = 255 if key == "display_name" else 500
        return _clean_text(value, max_length=limit)

    @validates("password_hash", "is_service_account")
    def _ensure_password_consistency(
        self, key: str, value: str | bool | None
    ) -> str | bool | None:
        if key == "password_hash":
            if value and self.is_service_account:
                msg = "Service accounts must not have passwords"
                raise ValueError(msg)
            return value

        if value and self.password_hash:
            msg = "Service accounts must not have passwords"
            raise ValueError(msg)
        return value

    @property
    def label(self) -> str:
        return self.display_name or self.email

    @property
    def kind(self) -> str:
        return "service_account" if self.is_service_account else "user"


__all__ = ["User", "UserRole"]
