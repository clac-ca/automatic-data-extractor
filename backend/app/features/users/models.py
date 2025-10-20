"""SQLAlchemy models for ADE user identities."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.db import Base, TimestampMixin, ULIDPrimaryKeyMixin


def _normalise_email(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        msg = "Email must not be empty"
        raise ValueError(msg)
    return cleaned


def _canonicalise_email(value: str) -> str:
    return value.lower()


def _clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 255:
        return cleaned[:255]
    return cleaned


class User(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single identity model for humans and service accounts."""

    __tablename__ = "users"
    __ulid_field__ = "user_id"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_canonical: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_service_account: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    identities: Mapped[list["UserIdentity"]] = relationship(
        "UserIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    credential: Mapped["UserCredential | None"] = relationship(
        "UserCredential",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    principal: Mapped["Principal | None"] = relationship(
        "Principal",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )

    @validates("email")
    def _store_normalised_email(self, _key: str, value: str) -> str:
        cleaned = _normalise_email(value)
        self.email_canonical = _canonicalise_email(cleaned)
        return cleaned

    @validates("display_name")
    def _trim_display_name(self, _key: str, value: str | None) -> str | None:
        return _clean_display_name(value)

    @property
    def label(self) -> str:
        base = self.display_name or self.email
        if self.is_service_account:
            return base or "Service account"
        return base

    @property
    def password_hash(self) -> str | None:
        credential = getattr(self, "credential", None)
        if credential is None:
            return None
        return credential.password_hash


class UserCredential(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed password secret associated with a user."""

    __tablename__ = "user_credentials"
    __ulid_field__ = "credential_id"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    last_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship("User", back_populates="credential")

    __table_args__ = (UniqueConstraint("user_id"),)


class UserIdentity(ULIDPrimaryKeyMixin, TimestampMixin, Base):
    """External identity mapping for SSO and federated logins."""

    __tablename__ = "user_identities"
    __ulid_field__ = "identity_id"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship("User", back_populates="identities")

    __table_args__ = (UniqueConstraint("provider", "subject"),)


__all__ = ["User", "UserIdentity", "UserCredential"]
