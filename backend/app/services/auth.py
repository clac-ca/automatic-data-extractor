"""Authentication helpers, dependencies, and CLI utilities."""

from __future__ import annotations

import argparse
import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from typing import Annotated, Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db, get_sessionmaker
from ..models import User, UserRole

logger = logging.getLogger(__name__)

_OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="/auth/token")

_SALT_BYTES = 16
_KEY_LEN = 32
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Decoded contents of an access token."""

    user_id: str
    email: str
    role: UserRole
    issued_at: datetime
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


_OPEN_ACCESS_USER = User(
    user_id="anonymous",
    email="anonymous@example.com",
    password_hash=None,
    is_active=True,
    role=UserRole.ADMIN,
)


def _encode_token(user: User, settings: config.Settings, *, expires_delta: timedelta | None) -> str:
    if not settings.jwt_secret_key:
        raise RuntimeError("ADE_JWT_SECRET_KEY must be configured when auth is enabled")

    issued_at = _now()
    expires_at = issued_at + (expires_delta or timedelta(minutes=settings.access_token_exp_minutes))
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "role": user.role.value,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User, settings: config.Settings, *, expires_delta: timedelta | None = None) -> str:
    """Generate a signed access token for the supplied user."""

    return _encode_token(user, settings, expires_delta=expires_delta)


def decode_access_token(token: str, settings: config.Settings) -> TokenPayload:
    """Return token contents or raise when invalid."""

    if not settings.jwt_secret_key:
        raise RuntimeError("ADE_JWT_SECRET_KEY must be configured when auth is enabled")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    try:
        user_id = str(payload["sub"])
        email = str(payload.get("email", ""))
        role = UserRole(str(payload.get("role", UserRole.VIEWER.value)))
        issued_at = datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc)
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload") from exc

    return TokenPayload(
        user_id=user_id,
        email=email,
        role=role,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def authenticate_user(db: Session, *, email: str, password: str) -> User | None:
    """Return the authenticated user or ``None`` when credentials are invalid."""

    candidate = db.query(User).filter(User.email == email).one_or_none()
    if candidate is None or not candidate.is_active:
        return None
    if candidate.password_hash is None:
        return None
    if not verify_password(password, candidate.password_hash):
        return None
    return candidate


async def get_current_user(
    token: Annotated[str, Depends(_OAUTH2_SCHEME)],
    db: Session = Depends(get_db),
    settings: config.Settings = Depends(config.get_settings),
) -> User:
    """Resolve the current user from a bearer token."""

    if settings.auth_disabled:
        return _OPEN_ACCESS_USER

    details = decode_access_token(token, settings)
    user = db.get(User, details.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has administrator privileges."""

    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Administrator privileges required")
    return user


def event_actor_from_user(user: User) -> dict[str, str]:
    """Return default event actor metadata for the supplied user."""

    return {
        "actor_type": "user",
        "actor_id": user.user_id,
        "actor_label": user.email,
    }


def validate_settings(settings: config.Settings) -> None:
    """Validate that authentication is correctly configured."""

    if settings.auth_disabled:
        logger.warning("Authentication is disabled; all requests are treated as anonymous")
        return

    if not settings.jwt_secret_key:
        raise RuntimeError("ADE_JWT_SECRET_KEY is required when authentication is enabled")


def clear_caches() -> None:  # pragma: no cover - compatibility shim
    """Placeholder to satisfy legacy test helpers."""

    return None


def _create_user(db: Session, *, email: str, password: str, role: UserRole) -> User:
    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing is not None:
        msg = f"User with email {email!r} already exists"
        raise ValueError(msg)

    user = User(email=email, password_hash=hash_password(password), role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created user", extra={"user_id": user.user_id, "email": user.email, "role": user.role})
    return user


def _set_password(db: Session, *, email: str, password: str) -> None:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        msg = f"No user found for email {email!r}"
        raise ValueError(msg)
    user.password_hash = hash_password(password)
    db.commit()
    logger.info("Updated password", extra={"user_id": user.user_id, "email": user.email})


def _list_users(db: Session) -> list[User]:
    return list(db.query(User).order_by(User.email).all())


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register authentication management commands."""

    parser = subparsers.add_parser("auth", help="Authentication management commands")
    commands = parser.add_subparsers(dest="command", required=True)

    create_parser = commands.add_parser("create-user", help="Create a new user")
    create_parser.add_argument("email", help="Email address")
    create_parser.add_argument("password", help="Initial password")
    create_parser.add_argument(
        "--role",
        choices=[role.value for role in UserRole],
        default=UserRole.VIEWER.value,
        help="Role to assign (defaults to viewer)",
    )
    create_parser.set_defaults(handler=_cli_create_user)

    password_parser = commands.add_parser("set-password", help="Update an existing user's password")
    password_parser.add_argument("email", help="Email address")
    password_parser.add_argument("password", help="New password")
    password_parser.set_defaults(handler=_cli_set_password)

    list_parser = commands.add_parser("list-users", help="List registered users")
    list_parser.set_defaults(handler=_cli_list_users)


def _with_session(func: Callable[[Session, argparse.Namespace], None]) -> Callable[[argparse.Namespace], int]:
    def _wrapper(args: argparse.Namespace) -> int:
        session_factory = get_sessionmaker()
        with session_factory() as db:
            func(db, args)
        return 0

    return _wrapper


@_with_session
def _cli_create_user(db: Session, args: argparse.Namespace) -> None:
    role = UserRole(args.role)
    _create_user(db, email=args.email, password=args.password, role=role)


@_with_session
def _cli_set_password(db: Session, args: argparse.Namespace) -> None:
    _set_password(db, email=args.email, password=args.password)


@_with_session
def _cli_list_users(db: Session, args: argparse.Namespace) -> None:  # pragma: no cover - CLI output
    users = _list_users(db)
    for user in users:
        status = "active" if user.is_active else "inactive"
        print(f"{user.email} ({user.role.value}) [{status}]")


__all__ = [
    "TokenPayload",
    "authenticate_user",
    "create_access_token",
    "decode_access_token",
    "event_actor_from_user",
    "get_current_user",
    "hash_password",
    "clear_caches",
    "register_cli",
    "require_admin",
    "validate_settings",
    "verify_password",
]
