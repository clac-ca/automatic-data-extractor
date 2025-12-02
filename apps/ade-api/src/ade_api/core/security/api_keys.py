"""API key generation and hashing helpers."""

from __future__ import annotations

import base64
import hashlib
import secrets


def generate_api_key_prefix(length: int = 12) -> str:
    """Return a URL-safe prefix for display/logging."""

    if length <= 0:
        raise ValueError("Prefix length must be positive")
    # token_urlsafe emits base64url characters; slice to the requested length.
    return secrets.token_urlsafe(length)[:length]


def generate_api_key_secret(length: int = 32) -> str:
    """Return the secret component of an API key."""

    if length <= 0:
        raise ValueError("Secret length must be positive")
    return secrets.token_urlsafe(length)


def hash_api_key_secret(secret: str) -> str:
    """Return a deterministic base64url hash for the secret."""

    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

