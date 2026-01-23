"""SQLAlchemy custom column types (SQL Server/Azure SQL; SQLite test-only).

- GUID: UUID stored as UNIQUEIDENTIFIER on SQL Server, CHAR(36) on SQLite.
- UTCDateTime: timezone-aware datetimes normalized to UTC.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.types import CHAR, DateTime, TypeDecorator

__all__ = ["GUID", "UTCDateTime"]


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID.

    - SQL Server: UNIQUEIDENTIFIER
    - SQLite: CHAR(36)
    """

    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mssql":
            from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        return dialect.type_descriptor(CHAR(36))

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
