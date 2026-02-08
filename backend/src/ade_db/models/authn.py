"""Authentication persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ade_db import GUID, Base, UTCDateTime, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from .user import User

AUTH_SESSION_AUTH_METHOD_VALUES = ("password", "sso", "unknown")


class AuthSession(UUIDPrimaryKeyMixin, Base):
    """Hashed browser session token."""

    __tablename__ = "auth_sessions"

    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    auth_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default="unknown",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="auth_sessions")

    __table_args__ = (
        CheckConstraint(
            f"auth_method IN {AUTH_SESSION_AUTH_METHOD_VALUES}",
            name="ck_auth_sessions_auth_method",
        ),
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )


class PasswordResetToken(UUIDPrimaryKeyMixin, Base):
    """One-time token for password reset."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_password_reset_tokens_user_id", "user_id"),
        Index("ix_password_reset_tokens_expires_at", "expires_at"),
    )


class UserMfaTotp(Base):
    """TOTP enrollment for a user."""

    __tablename__ = "user_mfa_totp"

    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        primary_key=True,
    )
    secret_enc: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )
    enrolled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    recovery_code_hashes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        nullable=False,
        default=list,
        server_default="[]",
    )

    user: Mapped["User"] = relationship("User")


class MfaChallenge(UUIDPrimaryKeyMixin, Base):
    """One-time MFA challenge token."""

    __tablename__ = "mfa_challenges"

    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    challenge_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_mfa_challenges_user_id", "user_id"),
        Index("ix_mfa_challenges_expires_at", "expires_at"),
    )


__all__ = [
    "AUTH_SESSION_AUTH_METHOD_VALUES",
    "AuthSession",
    "PasswordResetToken",
    "UserMfaTotp",
    "MfaChallenge",
]
