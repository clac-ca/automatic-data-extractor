"""Password hashing helpers."""

from __future__ import annotations

import base64
import hashlib
import secrets
from hmac import compare_digest

_SALT_BYTES = 16
_KEY_LEN = 32
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    """Return an scrypt hash for the supplied password."""

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
    return "scrypt$%d$%d$%d$%s$%s" % (
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        _encode(salt),
        _encode(key),
    )


def verify_password(password: str, hashed: str) -> bool:
    """Return ``True`` when the supplied password matches the stored hash."""

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

    return compare_digest(candidate, expected)


__all__ = ["hash_password", "verify_password"]
