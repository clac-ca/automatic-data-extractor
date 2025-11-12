"""Security helpers for authentication and authorisation."""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from fastapi import HTTPException, status


@dataclass(slots=True)
class TokenPayload:
    """Decoded contents of an issued authentication token."""

    user_id: str
    email: str
    issued_at: datetime
    expires_at: datetime
    token_type: Literal["access", "refresh"]
    session_id: str
    csrf_hash: str | None = None


_SALT_BYTES = 16
_KEY_LEN = 32
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1

_API_KEY_PREFIX_LEN = 8
_API_KEY_SECRET_BYTES = 32


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    """Hash ``password`` using scrypt with a random salt."""

    candidate = password.strip()
    if not candidate:
        msg = "Password must not be empty"
        raise ValueError(msg)

    salt = secrets.token_bytes(_SALT_BYTES)
    key = hashlib.scrypt(
        candidate.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LEN,
    )
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
        f"{_encode(salt)}${_encode(key)}"
    )


def verify_password(password: str, hashed: str) -> bool:
    """Return ``True`` if ``password`` matches ``hashed``."""

    try:
        _, n_str, r_str, p_str, salt_b64, key_b64 = hashed.split("$", 5)
        n = int(n_str)
        r = int(r_str)
        p = int(p_str)
        salt = _decode(salt_b64)
        expected = _decode(key_b64)
    except (ValueError, TypeError):
        return False

    try:
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
        )
    except ValueError:
        return False

    return secrets.compare_digest(candidate, expected)


def create_signed_token(
    *,
    user_id: str,
    email: str,
    session_id: str,
    token_type: Literal["access", "refresh"],
    secret: str,
    algorithm: str,
    expires_delta: timedelta,
    csrf_hash: str | None = None,
) -> str:
    """Return a signed JWT for the supplied identity and session."""

    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "sid": session_id,
        "typ": token_type,
    }
    if csrf_hash:
        payload["csrf"] = csrf_hash
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_signed_token(*, token: str, secret: str, algorithms: Sequence[str]) -> TokenPayload:
    """Decode ``token`` and return the parsed payload."""

    data = jwt.decode(token, secret, algorithms=list(algorithms))

    issued_at = datetime.fromtimestamp(int(data["iat"]), tz=UTC)
    expires_at = datetime.fromtimestamp(int(data["exp"]), tz=UTC)
    token_type = str(data.get("typ", "")).lower()
    if token_type not in {"access", "refresh"}:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unsupported token type")
    session_id = str(data.get("sid", "")).strip()
    if not session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
    csrf_raw = data.get("csrf")
    csrf_hash = str(csrf_raw) if csrf_raw is not None else None
    return TokenPayload(
        user_id=str(data["sub"]),
        email=str(data.get("email", "")),
        issued_at=issued_at,
        expires_at=expires_at,
        token_type=token_type,  # type: ignore[arg-type]
        session_id=session_id,
        csrf_hash=csrf_hash,
    )


def generate_api_key_components() -> tuple[str, str]:
    """Return a prefix/secret pair for a new API key."""

    prefix = secrets.token_hex(_API_KEY_PREFIX_LEN // 2)
    secret = secrets.token_urlsafe(_API_KEY_SECRET_BYTES)
    return prefix, secret


def hash_api_key(secret: str) -> str:
    """Return a deterministic hash for the secret component of an API key."""

    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return _encode(digest)


def hash_csrf_token(token: str) -> str:
    """Return a hex digest for CSRF token comparisons."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = [
    "TokenPayload",
    "hash_password",
    "hash_api_key",
    "hash_csrf_token",
    "verify_password",
    "create_signed_token",
    "decode_signed_token",
    "generate_api_key_components",
]
