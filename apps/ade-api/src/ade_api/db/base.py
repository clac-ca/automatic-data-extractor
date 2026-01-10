"""Declarative base + naming convention + common mixins."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """App-managed UTC timestamps.

    Keeps behavior consistent across SQLite and SQL Server without relying on DB triggers.
    """

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
