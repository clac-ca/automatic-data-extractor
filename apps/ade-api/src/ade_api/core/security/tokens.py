"""JWT helpers for decoding bearer tokens."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import jwt


def decode_token(token: str, *, secret: str, algorithms: Sequence[str]) -> dict[str, Any]:
    """Decode a JWT and return its payload."""

    return jwt.decode(token, secret, algorithms=list(algorithms))
