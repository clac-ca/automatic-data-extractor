"""Declarative base + naming convention + common mixins."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, NAMING_CONVENTION, metadata
from .types import GUID, UTCDateTime

__all__ = [
    "NAMING_CONVENTION",
    "metadata",
    "Base",
    "utc_now",
    "UUIDPrimaryKeyMixin",
    "TimestampMixin",
]


def utc_now() -> datetime:
    return datetime.now(UTC)


class UUIDPrimaryKeyMixin:
    """Standard GUID primary key."""

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        server_default=text("uuidv7()"),
    )


class TimestampMixin:
    """App-managed UTC timestamps.

    Keeps behavior consistent without relying on DB triggers.
    """

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
