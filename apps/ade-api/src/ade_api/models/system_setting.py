"""Persistence models for system-wide settings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from ade_api.db import Base, TimestampMixin


class SystemSetting(TimestampMixin, Base):
    """Key/value storage for instance-wide configuration flags."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB), default=dict, nullable=False
    )


__all__ = ["SystemSetting"]
