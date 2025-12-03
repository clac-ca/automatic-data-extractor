"""Database column types shared across ADE models."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.types import CHAR, TypeDecorator

__all__ = ["UUIDType"]


class UUIDType(TypeDecorator):
    """Platform-agnostic UUID storage.

    Uses native UUID types on PostgreSQL and SQL Server; falls back to a
    36-character string representation elsewhere. Values are always returned
    to Python as ``uuid.UUID`` objects.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any):
        name = dialect.name
        if name in {"postgresql", "postgres"}:
            from sqlalchemy.dialects.postgresql import UUID

            return dialect.type_descriptor(UUID(as_uuid=True))
        if name == "mssql":
            from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect: Any):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

    @property
    def python_type(self) -> type[uuid.UUID]:
        return uuid.UUID
