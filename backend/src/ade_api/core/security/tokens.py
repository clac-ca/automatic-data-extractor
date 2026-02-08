"""Token helpers for opaque tokens and optional JWT decoding."""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Sequence
from typing import Any

import jwt


def decode_token(
    token: str,
    *,
    secret: str,
    algorithms: Sequence[str],
    audience: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Decode a JWT and return its payload."""

    if audience:
        return jwt.decode(
            token,
            secret,
            algorithms=list(algorithms),
            audience=list(audience),
        )
    return jwt.decode(
        token,
        secret,
        algorithms=list(algorithms),
        options={"verify_aud": False},
    )


def mint_opaque_token(length: int = 48) -> str:
    """Return a random opaque token suitable for cookies or one-time links."""

    if length <= 0:
        raise ValueError("Token length must be positive")
    return secrets.token_urlsafe(length)


def hash_opaque_token(token: str) -> str:
    """Hash an opaque token for at-rest storage."""

    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
