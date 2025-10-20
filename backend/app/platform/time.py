"""Timezone-aware datetime helpers."""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["utc_now"]


def utc_now() -> datetime:
    """Return the current UTC time with timezone information."""

    return datetime.now(tz=UTC)

