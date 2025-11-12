"""Reusable SQLAlchemy mixins and helpers for ADE models."""

from __future__ import annotations

from datetime import datetime
from apps.api.app.shared.core.ids import generate_ulid
from apps.api.app.shared.core.time import utc_now
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

__all__ = ["generate_ulid", "TimestampMixin", "ULIDPrimaryKeyMixin"]


class ULIDPrimaryKeyMixin:
    """Mixin that supplies a ULID-backed primary key column."""

    @declared_attr.directive
    def id(cls) -> Mapped[str]:  # noqa: N805 - SQLAlchemy declared attr
        return mapped_column(
            "id",
            String(26),
            primary_key=True,
            default=generate_ulid,
        )


class TimestampMixin:
    """Mixin that records created/updated timestamps as timezone-aware datetimes."""

    @staticmethod
    def _timestamp() -> datetime:
        return utc_now()

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
