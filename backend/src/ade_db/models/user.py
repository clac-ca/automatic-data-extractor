"""Canonical user and auth-related models shared across auth and RBAC."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from ade_db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from .authn import AuthSession


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


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single identity model for humans."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    given_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    surname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    office_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mobile_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_phones: Mapped[str | None] = mapped_column(Text(), nullable=True)
    employee_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employee_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="internal",
        server_default=text("'internal'"),
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    is_service_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    auth_sessions: Mapped[list[AuthSession]] = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_users_source_external"),
    )

    @validates("email")
    def _store_normalised_email(self, _key: str, value: str) -> str:
        cleaned = _normalise_email(value)
        self.email_normalized = _canonicalise_email(cleaned)
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


class OAuthAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """External identity mapping for SSO and federated logins."""

    __tablename__ = "oauth_accounts"

    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    oauth_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    access_token: Mapped[str] = mapped_column(Text(), nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (
        UniqueConstraint(
            "oauth_name",
            "account_id",
            name="uq_oauth_accounts_name_account",
        ),
    )


__all__ = ["User", "OAuthAccount"]
