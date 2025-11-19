"""Identifier helpers for ADE."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field
from ulid import ULID

__all__ = ["ULID_PATTERN", "ULIDStr", "generate_ulid"]

ULID_PATTERN = r"[0-9A-HJKMNP-TV-Z]{26}"
ULID_DESCRIPTION = "ULID (26-character string)."

# Reusable Annotated type to keep ULID validation consistent across schemas.
ULIDStr = Annotated[
    str,
    Field(
        min_length=26,
        max_length=26,
        pattern=ULID_PATTERN,
        description=ULID_DESCRIPTION,
    ),
]


def generate_ulid() -> str:
    """Return a lexicographically sortable ULID string."""

    return str(ULID())
