"""Minimal TOTP helpers (RFC 6238 / 4226)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from collections.abc import Iterable

DEFAULT_DIGITS = 6
DEFAULT_PERIOD_SECONDS = 30


def generate_totp_secret(length: int = 32) -> str:
    """Generate a base32 secret for TOTP."""

    # 20 raw bytes -> 32 base32 chars without padding.
    raw = secrets.token_bytes(max(20, length // 2))
    encoded = base64.b32encode(raw).decode("ascii").rstrip("=")
    return encoded[:length]


def _normalize_secret(secret: str) -> bytes:
    candidate = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(candidate) % 8) % 8)
    return base64.b32decode(candidate + padding, casefold=True)


def _hotp(secret: bytes, counter: int, *, digits: int = DEFAULT_DIGITS) -> str:
    message = struct.pack(">Q", counter)
    digest = hmac.new(secret, message, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code_int % (10**digits)).zfill(digits)


def totp_now(
    secret: str,
    *,
    timestamp: int | None = None,
    period_seconds: int = DEFAULT_PERIOD_SECONDS,
    digits: int = DEFAULT_DIGITS,
) -> str:
    ts = int(time.time() if timestamp is None else timestamp)
    counter = ts // period_seconds
    secret_bytes = _normalize_secret(secret)
    return _hotp(secret_bytes, counter, digits=digits)


def verify_totp(
    secret: str,
    code: str,
    *,
    timestamp: int | None = None,
    period_seconds: int = DEFAULT_PERIOD_SECONDS,
    digits: int = DEFAULT_DIGITS,
    valid_window: int = 1,
) -> bool:
    candidate = "".join(ch for ch in code.strip() if ch.isdigit())
    if len(candidate) != digits:
        return False
    ts = int(time.time() if timestamp is None else timestamp)
    counter = ts // period_seconds
    secret_bytes = _normalize_secret(secret)
    for delta in range(-valid_window, valid_window + 1):
        if hmac.compare_digest(_hotp(secret_bytes, counter + delta, digits=digits), candidate):
            return True
    return False


def generate_recovery_codes(*, count: int = 8, groups: int = 2, group_len: int = 4) -> list[str]:
    """Generate user-facing recovery codes."""

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    codes: list[str] = []
    while len(codes) < count:
        parts = []
        for _ in range(groups):
            parts.append("".join(secrets.choice(alphabet) for _ in range(group_len)))
        code = "-".join(parts)
        if code not in codes:
            codes.append(code)
    return codes


def normalize_recovery_code(code: str) -> str:
    """Normalize recovery-code input to the canonical persisted form."""

    return "".join(ch for ch in code.strip().upper() if ch.isalnum())


def hash_recovery_codes(codes: Iterable[str]) -> list[str]:
    """Hash recovery codes for at-rest storage."""

    hashed: list[str] = []
    for code in codes:
        normalized = normalize_recovery_code(code)
        if not normalized:
            continue
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()
        hashed.append(base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="))
    return hashed


def verify_recovery_code(candidate: str, hashes: Iterable[str]) -> bool:
    normalized = normalize_recovery_code(candidate)
    if len(normalized) != 8:
        return False
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return any(hmac.compare_digest(encoded, expected) for expected in hashes)
