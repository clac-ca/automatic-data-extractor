"""Shared helpers for authentication features."""

from __future__ import annotations


def normalise_email(value: str) -> str:
    """Return a canonical representation for email comparisons."""

    candidate = value.strip()
    if not candidate:
        msg = "Email must not be empty"
        raise ValueError(msg)
    return candidate.lower()


def normalise_api_key_label(value: str | None) -> str | None:
    """Return a trimmed API key label limited to 100 characters."""

    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 100:
        return cleaned[:100]
    return cleaned


__all__ = [
    "normalise_api_key_label",
    "normalise_email",
]

