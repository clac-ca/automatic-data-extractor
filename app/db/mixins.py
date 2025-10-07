"""Reusable SQLAlchemy mixins and helpers for ADE models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from ulid import ULID

__all__ = [
    "generate_ulid",
    "TimestampMixin",
    "ULIDPrimaryKeyMixin",
]


def generate_ulid() -> str:
    """Return a lexicographically sortable ULID string."""

    return str(ULID())


class ULIDPrimaryKeyMixin:
    """Mixin that supplies a ULID-backed primary key column."""

    __ulid_field__: ClassVar[str] = "id"

    @declared_attr.directive
    def id(cls) -> Mapped[str]:  # noqa: N805 - SQLAlchemy declared attr
        column_name = getattr(cls, "__ulid_field__", "id")
        return mapped_column(
            column_name,
            String(26),
            primary_key=True,
            default=generate_ulid,
        )


class TimestampMixin:
    """Mixin that records created/updated timestamps as timezone-aware datetimes."""

    @staticmethod
    def _timestamp() -> datetime:
        return datetime.now(tz=UTC)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_timestamp,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_timestamp,
        onupdate=_timestamp,
    )
