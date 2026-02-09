"""Identifier helpers for ADE."""

from __future__ import annotations

import secrets
import threading
import time
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


_UUID7_LOCK = threading.Lock()
_UUID7_LAST_TS_MS: int = -1
_UUID7_LAST_RAND: int = 0

_UUID7_RAND_BITS = 74
_UUID7_RAND_MASK = (1 << _UUID7_RAND_BITS) - 1
_UUID7_RAND_B_MASK = (1 << 62) - 1


def _uuid7_randbits(bits: int) -> int:
    nbytes = (bits + 7) // 8
    value = int.from_bytes(secrets.token_bytes(nbytes), "big")
    return value & ((1 << bits) - 1)


def generate_uuid7() -> uuid.UUID:
    """Return a sortable UUIDv7 for ADE identifiers (RFC 9562).

    We implement UUIDv7 directly to keep runtime behavior consistent across
    environments, even though :func:`uuid.uuid7` is available in Python 3.14+.
    """

    global _UUID7_LAST_TS_MS, _UUID7_LAST_RAND

    ts_ms = time.time_ns() // 1_000_000
    with _UUID7_LOCK:
        if ts_ms > _UUID7_LAST_TS_MS:
            _UUID7_LAST_TS_MS = ts_ms
            _UUID7_LAST_RAND = _uuid7_randbits(_UUID7_RAND_BITS)
        else:
            ts_ms = _UUID7_LAST_TS_MS
            _UUID7_LAST_RAND = (_UUID7_LAST_RAND + 1) & _UUID7_RAND_MASK

            if _UUID7_LAST_RAND == 0:
                while True:
                    candidate_ts = time.time_ns() // 1_000_000
                    if candidate_ts > _UUID7_LAST_TS_MS:
                        ts_ms = candidate_ts
                        _UUID7_LAST_TS_MS = candidate_ts
                        _UUID7_LAST_RAND = _uuid7_randbits(_UUID7_RAND_BITS)
                        break

        rand_a = _UUID7_LAST_RAND >> 62
        rand_b = _UUID7_LAST_RAND & _UUID7_RAND_B_MASK

        value = (ts_ms & 0xFFFFFFFFFFFF) << 80
        value |= 0x7 << 76  # version 7
        value |= (rand_a & 0xFFF) << 64
        value |= 0b10 << 62  # variant (RFC 4122)
        value |= rand_b

    return uuid.UUID(int=value)
