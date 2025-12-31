"""Password hashing helpers (argon2 via pwdlib)."""

from __future__ import annotations

from fastapi_users.password import PasswordHelper

_password_helper = PasswordHelper()


def hash_password(password: str) -> str:
    """Hash ``password`` using the configured password helper."""

    candidate = password.strip()
    if not candidate:
        msg = "Password must not be empty"
        raise ValueError(msg)

    return _password_helper.hash(candidate)


def verify_password(password: str, hashed: str) -> bool:
    """Return ``True`` if ``password`` matches ``hashed``."""

    try:
        verified, _ = _password_helper.verify_and_update(password, hashed)
    except Exception:
        return False
    return verified


__all__ = ["hash_password", "verify_password"]
