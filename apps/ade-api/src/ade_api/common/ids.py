"""Identifier helpers for ADE."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from pydantic import Field

__all__ = ["UUID_DESCRIPTION", "UUIDStr", "generate_uuid7"]

UUID_DESCRIPTION = "UUIDv7 (RFC 9562) generated in the application layer."

# Reusable Annotated type to keep UUID validation consistent across schemas.
UUIDStr = Annotated[
    uuid.UUID,
    Field(
        description=UUID_DESCRIPTION,
    ),
]


def _resolve_uuid7() -> Callable[[], uuid.UUID]:
    """Return a callable that produces a UUIDv7, falling back to uuid4 when absent."""

    maybe_uuid7 = getattr(uuid, "uuid7", None)
    if callable(maybe_uuid7):
        return maybe_uuid7
    return uuid.uuid4


_uuid7_factory = _resolve_uuid7()


def generate_uuid7() -> uuid.UUID:
    """Return a sortable UUID for ADE identifiers (prefers RFC 9562 uuid7)."""

    return _uuid7_factory()
