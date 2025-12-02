"""Identifier helpers for ADE."""

from __future__ import annotations

import uuid
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


def generate_uuid7() -> uuid.UUID:
    """Return an RFC 9562 UUIDv7 generated in the application layer."""

    if not hasattr(uuid, "uuid7"):  # pragma: no cover - guard for unexpected runtimes
        msg = "Python 3.14+ is required for uuid.uuid7()"
        raise RuntimeError(msg)
    return uuid.uuid7()
