"""Reusable SQLAlchemy mixins and helpers for ADE models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from ade_api.shared.core.ids import generate_uuid7
from ade_api.shared.core.time import utc_now
from ade_api.shared.db.types import UUIDType

__all__ = ["TimestampMixin", "UUIDPrimaryKeyMixin", "generate_uuid7"]


class UUIDPrimaryKeyMixin:
    """Mixin that supplies a UUIDv7-backed primary key column."""

    @declared_attr.directive
    def id(cls) -> Mapped[UUID]:  # noqa: N805 - SQLAlchemy declared attr
        return mapped_column(
            "id",
            UUIDType(),
            primary_key=True,
            default=generate_uuid7,
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
