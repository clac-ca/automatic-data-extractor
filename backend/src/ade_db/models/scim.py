"""SCIM provisioning token persistence models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ade_db import GUID, Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


class ScimToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Bearer token metadata used to authenticate SCIM provisioning requests."""

    __tablename__ = "scim_tokens"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    hashed_secret: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="NO ACTION"),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (
        Index("ix_scim_tokens_created_by_user_id", "created_by_user_id"),
        Index("ix_scim_tokens_revoked_at", "revoked_at"),
        Index("ix_scim_tokens_last_used_at", "last_used_at"),
    )


__all__ = ["ScimToken"]
