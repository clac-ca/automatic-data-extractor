"""Shared helpers for handling HTTP ETag headers."""

from __future__ import annotations


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
    """Quote a canonical ETag for use in HTTP headers/payloads."""
    token = canonicalize_etag(value)
    if token is None:
        return None
    return f'"{token}"'


__all__ = ["canonicalize_etag", "format_etag"]
