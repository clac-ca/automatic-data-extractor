"""Secret encryption helpers for manifest storage."""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.app.shared.core.config import Settings, get_settings

from .schemas import ManifestSecretCipher

_SECRET_HKDF_INFO = b"ade.config.secret.v1"


def encrypt_secret(
    value: str,
    *,
    settings: Settings | None = None,
    key_id: str = "default",
) -> ManifestSecretCipher:
    """Encrypt ``value`` into a manifest secret envelope."""

    if not isinstance(value, str) or not value:
        raise ValueError("value must be a non-empty string")

    resolved_settings = settings or get_settings()
    master_key = resolved_settings.secret_key_bytes

    salt = os.urandom(16)
    nonce = os.urandom(12)
    derived_key = _derive_key(master_key, salt)
    aesgcm = AESGCM(derived_key)
    ciphertext = aesgcm.encrypt(nonce, value.encode("utf-8"), _associated_data(key_id))

    return ManifestSecretCipher(
        key_id=key_id,
        nonce=_b64encode(nonce),
        salt=_b64encode(salt),
        ciphertext=_b64encode(ciphertext),
        created_at=datetime.now(timezone.utc),
    )


def decrypt_secret(
    payload: ManifestSecretCipher,
    *,
    settings: Settings | None = None,
) -> str:
    """Decrypt a manifest secret payload into plaintext."""

    resolved_settings = settings or get_settings()
    master_key = resolved_settings.secret_key_bytes

    nonce = _b64decode(payload.nonce)
    salt = _b64decode(payload.salt)
    ciphertext = _b64decode(payload.ciphertext)

    derived_key = _derive_key(master_key, salt)
    aesgcm = AESGCM(derived_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, _associated_data(payload.key_id))
    return plaintext.decode("utf-8")


def _derive_key(master_key: bytes, salt: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_SECRET_HKDF_INFO,
    )
    return hkdf.derive(master_key)


def _associated_data(key_id: str) -> bytes:
    return b"|".join((b"ade.secret", key_id.encode("utf-8")))


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"), validate=True)


__all__ = ["decrypt_secret", "encrypt_secret"]
