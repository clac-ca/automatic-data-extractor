"""JWT helpers for issuing and decoding access/refresh tokens."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt


def _now() -> datetime:
    return datetime.now(UTC)


def _create_token(
    payload: dict[str, Any],
    *,
    secret: str,
    algorithm: str,
    ttl_seconds: int,
) -> str:
    issued_at = _now()
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    claims = dict(payload)
    claims.update({
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    })
    return jwt.encode(claims, secret, algorithm=algorithm)


def create_access_token(
    payload: dict[str, Any],
    *,
    secret: str,
    algorithm: str,
    ttl_seconds: int,
) -> str:
    """Issue an access token with a TTL."""

    data = dict(payload)
    data["typ"] = "access"
    return _create_token(
        data,
        secret=secret,
        algorithm=algorithm,
        ttl_seconds=ttl_seconds,
    )


def create_refresh_token(
    payload: dict[str, Any],
    *,
    secret: str,
    algorithm: str,
    ttl_seconds: int,
) -> str:
    """Issue a refresh token with a TTL."""

    data = dict(payload)
    data["typ"] = "refresh"
    return _create_token(
        data,
        secret=secret,
        algorithm=algorithm,
        ttl_seconds=ttl_seconds,
    )


def decode_token(token: str, *, secret: str, algorithms: Sequence[str]) -> dict[str, Any]:
    """Decode a JWT and return its payload."""

    return jwt.decode(token, secret, algorithms=list(algorithms))
