"""Declarative base + naming convention + common mixins."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .types import GUID, UTCDateTime

__all__ = [
    "NAMING_CONVENTION",
    "metadata",
    "Base",
    "utc_now",
    "UUIDPrimaryKeyMixin",
    "TimestampMixin",
]

NAMING_CONVENTION: dict[str, str] = {
    "ix": "%(table_name)s_%(column_0_name)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Declarative base using the global naming convention."""

    metadata = metadata


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
