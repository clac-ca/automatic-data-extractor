"""SQLAlchemy custom column types (SQL Server/Azure SQL only).

- GUID: UUID stored as UNIQUEIDENTIFIER.
- UTCDateTime: timezone-aware datetimes normalized to UTC.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.types import DateTime, TypeDecorator

__all__ = ["GUID", "UTCDateTime"]


class GUID(TypeDecorator):
    """SQL Server GUID/UUID (UNIQUEIDENTIFIER)."""

    impl = UNIQUEIDENTIFIER
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(UNIQUEIDENTIFIER())

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

    @property
    def python_type(self) -> type[uuid.UUID]:
        return uuid.UUID


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetime normalized to UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        return value

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        return value
