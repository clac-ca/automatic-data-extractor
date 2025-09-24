"""Security helpers for authentication and authorisation."""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any

import jwt
from fastapi import HTTPException, status

from ..users.models import UserRole


@dataclass(slots=True)
class TokenPayload:
    """Decoded contents of an access token."""

    user_id: str
    email: str
    role: UserRole
    issued_at: datetime
    expires_at: datetime


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


def create_access_token(
    *,
    user_id: str,
    email: str,
    role: UserRole,
    secret: str,
    algorithm: str,
    expires_delta: timedelta,
) -> str:
    """Return a signed JWT for the supplied identity."""

    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(*, token: str, secret: str, algorithms: Sequence[str]) -> TokenPayload:
    """Decode ``token`` and return the parsed payload."""

    data = jwt.decode(token, secret, algorithms=list(algorithms))

    issued_at = datetime.fromtimestamp(int(data["iat"]), tz=UTC)
    expires_at = datetime.fromtimestamp(int(data["exp"]), tz=UTC)
    role = UserRole(data["role"])
    return TokenPayload(
        user_id=str(data["sub"]),
        email=str(data.get("email", "")),
        role=role,
        issued_at=issued_at,
        expires_at=expires_at,
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


def access_control(
    *,
    permissions: Iterable[str] | None = None,
    require_workspace: bool = False,
    require_admin: bool = False,
    allow_admin_override: bool = True,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator enforcing authorisation rules on class-based endpoints."""

    required = frozenset(permissions or [])

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            service = getattr(self, "service", None)
            if service is None:
                raise RuntimeError("access_control expects the view to expose 'service'")

            user = getattr(service, "current_user", None)
            if user is None:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

            user_role = getattr(user, "role", None)
            if allow_admin_override and user_role == UserRole.ADMIN:
                return await func(self, *args, **kwargs)

            if require_admin and user_role != UserRole.ADMIN:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="Administrator role required",
                )

            workspace = getattr(service, "current_workspace", None)
            if require_workspace and workspace is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Workspace context required",
                )

            if required:
                granted = getattr(service, "permissions", frozenset())
                if not required.issubset(granted):
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions",
                    )

            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "TokenPayload",
    "hash_password",
    "hash_api_key",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "access_control",
    "generate_api_key_components",
]
