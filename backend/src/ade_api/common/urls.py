"""URL sanitization helpers."""

from __future__ import annotations

from urllib.parse import urlparse


def sanitize_return_to(value: str | None) -> str | None:
    """Return a safe relative path or ``None`` when invalid."""

    if value is None:
        return None
    candidate = value.strip()
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in candidate):
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    return candidate


__all__ = ["sanitize_return_to"]
