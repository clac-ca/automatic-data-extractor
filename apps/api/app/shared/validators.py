from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime


def parse_csv_or_repeated(value: object) -> set[str] | None:
    """Normalise query values that may be CSV strings or repeated params."""

    if value is None:
        return None
    if isinstance(value, str):
        tokens = {segment.strip() for segment in value.split(",") if segment.strip()}
        return tokens or None
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        out: set[str] = set()
        for item in value:
            if isinstance(item, str):
                out.update(segment.strip() for segment in item.split(",") if segment.strip())
            else:
                out.add(str(item))
        return out or None
    return {str(value)}


def normalize_utc(dt: datetime | None) -> datetime | None:
    """Return ``dt`` coerced to UTC, treating naive datetimes as UTC."""

    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


__all__ = ["parse_csv_or_repeated", "normalize_utc"]
