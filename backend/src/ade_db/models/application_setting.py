"""Singleton application runtime settings model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Integer, SmallInteger, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from ade_db import GUID, Base, UTCDateTime, utc_now


class ApplicationSetting(Base):
    """Singleton row storing versioned runtime settings payload."""

    __tablename__ = "application_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        server_default=text("2"),
    )
    data: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("now()"),
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        GUID(),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_application_settings_singleton"),
        CheckConstraint(
            "jsonb_typeof(data) = 'object'",
            name="ck_application_settings_data_object",
        ),
    )


__all__ = ["ApplicationSetting"]
