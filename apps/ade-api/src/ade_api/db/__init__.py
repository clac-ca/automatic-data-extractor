"""Database plumbing (SQLAlchemy engines, sessions, base classes, types)."""

from .base import NAMING_CONVENTION, Base, metadata
from .engine import (
    attach_managed_identity,
    build_database_url,
    ensure_database_ready,
    get_engine,
    render_sync_url,
    reset_database_state,
)
from .mixins import TimestampMixin, UUIDPrimaryKeyMixin, generate_ulid, generate_uuid7
from .session import get_session, get_sessionmaker, reset_session_state
from .types import UUIDType

__all__ = [
    "Base",
    "NAMING_CONVENTION",
    "metadata",
    "attach_managed_identity",
    "build_database_url",
    "ensure_database_ready",
    "get_engine",
    "render_sync_url",
    "reset_database_state",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "generate_uuid7",
    "generate_ulid",
    "get_session",
    "get_sessionmaker",
    "reset_session_state",
    "UUIDType",
]
