"""HTTP helpers for idempotency headers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

from .service import IDEMPOTENCY_KEY_HEADER, normalize_idempotency_key


async def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias=IDEMPOTENCY_KEY_HEADER)] = None,
) -> str:
    return normalize_idempotency_key(idempotency_key)


__all__ = ["require_idempotency_key"]
