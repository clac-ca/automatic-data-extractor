"""Helpers for encrypting and decrypting secrets at rest."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ade_api.settings import Settings


def _derive_key(raw: str) -> bytes:
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _resolve_key(settings: Settings) -> str:
    if settings.sso_encryption_key is not None:
        return settings.sso_encryption_key.get_secret_value()
    return settings.secret_key_value


def encrypt_secret(value: str, settings: Settings) -> str:
    key = _derive_key(_resolve_key(settings))
    fernet = Fernet(key)
    return fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str, settings: Settings) -> str:
    key = _derive_key(_resolve_key(settings))
    fernet = Fernet(key)
    try:
        return fernet.decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Unable to decrypt secret") from exc


__all__ = ["encrypt_secret", "decrypt_secret"]
