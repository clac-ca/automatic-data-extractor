"""Shared helpers for handling HTTP ETag headers."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def canonicalize_etag(value: str | None) -> str | None:
    """Return a normalized ETag token without weak prefixes or quotes."""

    if value is None:
        return None
    token = value.strip()
    if not token:
        return None
    if token.startswith("W/"):
        token = token[2:].strip()
    if token.startswith('"') and token.endswith('"'):
        token = token[1:-1]
    return token or None


def format_etag(value: str | None) -> str | None:
    """Quote a canonical ETag for use in HTTP headers."""

    token = canonicalize_etag(value)
    if token is None:
        return None
    return f'"{token}"'


def format_weak_etag(value: str | None) -> str | None:
    """Format a weak ETag with the W/ prefix."""

    token = canonicalize_etag(value)
    if token is None:
        return None
    return f'W/"{token}"'


def build_etag_token(*parts: Any) -> str:
    """Build a stable ETag token from component parts."""

    normalized: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, datetime):
            normalized.append(part.isoformat())
        else:
            normalized.append(str(part))
    return ":".join(normalized)


__all__ = [
    "build_etag_token",
    "canonicalize_etag",
    "format_etag",
    "format_weak_etag",
]
