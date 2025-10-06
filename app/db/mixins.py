"""Reusable SQLAlchemy mixins and helpers for ADE models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import String
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
    """Mixin that records created/updated timestamps as ISO-8601 strings."""

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(tz=UTC).isoformat(timespec="milliseconds")

    created_at: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=_timestamp,
    )
    updated_at: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=_timestamp,
        onupdate=_timestamp,
    )
