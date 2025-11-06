"""Identifier helpers for ADE."""

from __future__ import annotations

from ulid import ULID

__all__ = ["generate_ulid"]


def generate_ulid() -> str:
    """Return a lexicographically sortable ULID string."""

    return str(ULID())

