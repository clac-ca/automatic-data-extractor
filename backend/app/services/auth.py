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
from typing import Annotated, Any, Callable, Mapping
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db, get_sessionmaker
from ..models import APIKey, User, UserRole

logger = logging.getLogger(__name__)

_OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
_API_KEY_SCHEME = APIKeyHeader(name="X-API-Key", auto_error=False)

_SALT_BYTES = 16
_KEY_LEN = 32
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1

_API_KEY_PREFIX_LEN = 8
_API_KEY_SECRET_BYTES = 32

SSO_STATE_COOKIE = "ade_sso_state"
_SSO_STATE_TTL_SECONDS = 300

_OIDC_METADATA_CACHE: dict[str, "OIDCProviderMetadata"] = {}
_JWK_CLIENTS: dict[str, PyJWKClient] = {}


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Decoded contents of an access token."""

    user_id: str
    email: str
    role: UserRole
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class OIDCProviderMetadata:
    """Discovery metadata for an OpenID Connect issuer."""

    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


@dataclass(frozen=True, slots=True)
class SSOState:
    """Decoded state stored between the login redirect and callback."""

    state: str
    code_verifier: str
    nonce: str


@dataclass(frozen=True, slots=True)
class SSOLoginChallenge:
    """Redirect details returned when initiating an SSO login."""

    redirect_url: str
    state_token: str
    expires_in: int


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


def hash_api_key(secret: str) -> str:
    """Return a stable hash for the secret portion of an API key."""

    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return _encode(digest)


def _generate_api_key_components() -> tuple[str, str]:
    prefix = secrets.token_hex(_API_KEY_PREFIX_LEN // 2)
    secret = secrets.token_urlsafe(_API_KEY_SECRET_BYTES)
    return prefix, secret


def issue_api_key(
    db: Session,
    user: User,
    *,
    expires_at: datetime | None = None,
) -> tuple[str, APIKey]:
    """Create a new API key for the supplied user and return the raw secret."""

    prefix, secret = _generate_api_key_components()
    hashed = hash_api_key(secret)
    api_key = APIKey(
        user_id=user.user_id,
        token_prefix=prefix,
        token_hash=hashed,
        expires_at=expires_at.isoformat() if expires_at is not None else None,
    )
    db.add(api_key)
    db.flush()
    db.refresh(api_key)
    logger.info(
        "Issued API key",
        extra={"api_key_id": api_key.api_key_id, "user_id": user.user_id},
    )
    return f"{prefix}.{secret}", api_key


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _touch_api_key(
    api_key: APIKey,
    settings: config.Settings,
    request: Request,
) -> None:
    interval_seconds = settings.api_key_touch_interval_seconds
    now = _now()
    last_seen = _parse_timestamp(api_key.last_seen_at)
    if interval_seconds > 0 and last_seen is not None:
        if now - last_seen < timedelta(seconds=interval_seconds):
            return

    api_key.last_seen_at = now.isoformat()
    client = request.client
    if client and client.host:
        api_key.last_seen_ip = client.host[:45]
    user_agent = request.headers.get("user-agent")
    if user_agent:
        api_key.last_seen_user_agent = user_agent[:255]


def _authenticate_api_key(
    db: Session,
    settings: config.Settings,
    raw_key: str,
    *,
    request: Request,
) -> User | None:
    try:
        prefix, secret = raw_key.split(".", 1)
    except ValueError:
        return None

    candidate = db.query(APIKey).filter(APIKey.token_prefix == prefix).one_or_none()
    if candidate is None:
        return None

    if candidate.expires_at:
        expires_at = _parse_timestamp(candidate.expires_at)
        if expires_at is not None and expires_at < _now():
            return None

    expected = hash_api_key(secret)
    if not compare_digest(expected, candidate.token_hash):
        return None

    user = db.get(User, candidate.user_id)
    if user is None or not user.is_active:
        return None

    _touch_api_key(candidate, settings, request)
    return user


_OPEN_ACCESS_USER = User(
    user_id="anonymous",
    email="anonymous@example.com",
    password_hash=None,
    is_active=True,
    role=UserRole.ADMIN,
)


def _encode_token(
    user: User,
    settings: config.Settings,
    *,
    expires_delta: timedelta | None,
) -> str:
    if not settings.jwt_secret_key:
        raise RuntimeError("ADE_JWT_SECRET_KEY must be configured when auth is enabled")

    issued_at = _now()
    expires_at = issued_at + (
        expires_delta or timedelta(minutes=settings.access_token_exp_minutes)
    )
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "role": user.role.value,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(
    user: User,
    settings: config.Settings,
    *,
    expires_delta: timedelta | None = None,
) -> str:
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
    token: Annotated[str | None, Depends(_OAUTH2_SCHEME)],
    api_key: Annotated[str | None, Depends(_API_KEY_SCHEME)],
    request: Request,
    db: Session = Depends(get_db),
    settings: config.Settings = Depends(config.get_settings),
) -> User:
    """Resolve the current user from a bearer token or API key."""

    if settings.auth_disabled:
        return _OPEN_ACCESS_USER

    if token:
        details = decode_access_token(token, settings)
        user = db.get(User, details.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    if api_key:
        user = _authenticate_api_key(db, settings, api_key, request=request)
        if user is not None:
            return user
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


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


async def get_oidc_metadata(settings: config.Settings) -> OIDCProviderMetadata:
    """Return cached discovery metadata for the configured issuer."""

    issuer = settings.sso_issuer
    if not issuer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO not configured")

    cached = _OIDC_METADATA_CACHE.get(issuer)
    if cached is not None:
        return cached

    discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Failed to fetch OIDC discovery metadata",
            extra={"status_code": exc.response.status_code, "url": discovery_url},
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid SSO issuer") from exc
    except httpx.HTTPError as exc:
        logger.error("Unable to contact identity provider", exc_info=exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Unable to contact identity provider") from exc

    data = response.json()
    try:
        metadata = OIDCProviderMetadata(
            authorization_endpoint=str(data["authorization_endpoint"]),
            token_endpoint=str(data["token_endpoint"]),
            jwks_uri=str(data["jwks_uri"]),
        )
    except KeyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Incomplete SSO discovery document") from exc

    _OIDC_METADATA_CACHE[issuer] = metadata
    return metadata


def _build_code_verifier() -> str:
    return _encode(secrets.token_bytes(32))


def _build_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return _encode(digest)


def _encode_sso_state(
    *,
    state: str,
    code_verifier: str,
    nonce: str,
    settings: config.Settings,
    issued_at: datetime,
) -> str:
    if not settings.jwt_secret_key:
        raise RuntimeError("ADE_JWT_SECRET_KEY must be configured when auth is enabled")

    payload = {
        "state": state,
        "code_verifier": code_verifier,
        "nonce": nonce,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(seconds=_SSO_STATE_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def prepare_sso_login(settings: config.Settings) -> SSOLoginChallenge:
    """Generate the redirect URL and state required to initiate SSO login."""

    if not settings.sso_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SSO not configured")

    metadata = await get_oidc_metadata(settings)
    issued_at = _now()
    state = secrets.token_urlsafe(16)
    code_verifier = _build_code_verifier()
    code_challenge = _build_code_challenge(code_verifier)
    nonce = secrets.token_urlsafe(16)
    state_token = _encode_sso_state(
        state=state,
        code_verifier=code_verifier,
        nonce=nonce,
        settings=settings,
        issued_at=issued_at,
    )

    params = {
        "response_type": "code",
        "client_id": settings.sso_client_id,
        "redirect_uri": settings.sso_redirect_url,
        "scope": settings.sso_scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    redirect_url = f"{metadata.authorization_endpoint}?{urlencode(params)}"
    return SSOLoginChallenge(
        redirect_url=redirect_url,
        state_token=state_token,
        expires_in=_SSO_STATE_TTL_SECONDS,
    )


def decode_sso_state(token: str, settings: config.Settings) -> SSOState:
    """Validate and decode the stored login state."""

    if not settings.jwt_secret_key:
        raise RuntimeError("ADE_JWT_SECRET_KEY must be configured when auth is enabled")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "state", "code_verifier", "nonce"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="SSO state expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid SSO state") from exc

    return SSOState(
        state=str(payload["state"]),
        code_verifier=str(payload["code_verifier"]),
        nonce=str(payload["nonce"]),
    )


async def exchange_authorization_code(
    settings: config.Settings,
    *,
    code: str,
    code_verifier: str,
) -> Mapping[str, Any]:
    """Exchange the authorization code for provider tokens."""

    metadata = await get_oidc_metadata(settings)
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.sso_redirect_url,
        "code_verifier": code_verifier,
        "client_id": settings.sso_client_id,
    }

    auth: tuple[str, str] | None = None
    if settings.sso_client_secret:
        auth = (settings.sso_client_id or "", settings.sso_client_secret)
        payload["client_secret"] = settings.sso_client_secret

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                metadata.token_endpoint,
                data=payload,
                headers={"Accept": "application/json"},
                auth=auth,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "SSO token exchange failed",
            extra={"status_code": exc.response.status_code},
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="SSO token exchange failed") from exc
    except httpx.HTTPError as exc:
        logger.error("Unable to reach SSO token endpoint", exc_info=exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Unable to contact identity provider") from exc

    data = response.json()
    return data


def _get_jwk_client(jwks_uri: str) -> PyJWKClient:
    client = _JWK_CLIENTS.get(jwks_uri)
    if client is None:
        client = PyJWKClient(jwks_uri)
        _JWK_CLIENTS[jwks_uri] = client
    return client


def verify_jwt_via_jwks(
    token: str,
    jwks_uri: str,
    *,
    audience: str | None,
    issuer: str,
    nonce: str | None = None,
) -> Mapping[str, Any]:
    """Validate a JWT using the provider JWKS endpoint."""

    client = _get_jwk_client(jwks_uri)
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        options: dict[str, Any] = {"require": ["exp", "iat", "iss", "sub"]}
        if audience is not None:
            options["require"].append("aud")
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512"],
            audience=audience,
            issuer=issuer,
            options=options,
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid token from identity provider") from exc

    if nonce is not None and payload.get("nonce") != nonce:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid SSO nonce")

    return payload


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def resolve_sso_user(
    db: Session,
    *,
    provider: str,
    subject: str,
    email: str,
    email_verified: bool,
) -> User:
    """Resolve or create a user for the supplied SSO identity."""

    if not email_verified:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Email not verified by identity provider")

    normalised_email = _normalise_email(email)
    user = (
        db.query(User)
        .filter(User.sso_provider == provider, User.sso_subject == subject)
        .one_or_none()
    )
    if user is None:
        user = db.query(User).filter(User.email == normalised_email).one_or_none()
        if user is None:
            user = User(
                email=normalised_email,
                password_hash=None,
                role=UserRole.VIEWER,
                is_active=True,
                sso_provider=provider,
                sso_subject=subject,
            )
            db.add(user)
            db.flush()
            logger.info(
                "Provisioned user from SSO",
                extra={"user_id": user.user_id, "email": user.email, "provider": provider},
            )
        else:
            if not user.is_active:
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User account is disabled")
            user.sso_provider = provider
            user.sso_subject = subject
            if user.email != normalised_email:
                user.email = normalised_email
    else:
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User account is disabled")
        if user.email != normalised_email:
            user.email = normalised_email

    user.last_login_at = _now().isoformat()
    return user


def validate_settings(settings: config.Settings) -> None:
    """Validate that authentication is correctly configured."""

    if settings.auth_disabled:
        logger.warning("Authentication is disabled; all requests are treated as anonymous")
        return

    if not settings.jwt_secret_key:
        raise RuntimeError("ADE_JWT_SECRET_KEY is required when authentication is enabled")

    if settings.sso_enabled and not settings.sso_scope:
        raise RuntimeError("ADE_SSO_SCOPE must be provided when SSO is enabled")


def clear_caches() -> None:
    """Clear cached metadata for deterministic tests."""

    _OIDC_METADATA_CACHE.clear()
    _JWK_CLIENTS.clear()


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

    api_key_parser = commands.add_parser("create-api-key", help="Issue a new API key for a user")
    api_key_parser.add_argument("email", help="Email address")
    api_key_parser.add_argument(
        "--expires-in-days",
        type=int,
        default=None,
        help="Optional expiration window for the API key",
    )
    api_key_parser.set_defaults(handler=_cli_create_api_key)


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
        status_label = "active" if user.is_active else "inactive"
        print(f"{user.email} ({user.role.value}) [{status_label}]")


@_with_session
def _cli_create_api_key(db: Session, args: argparse.Namespace) -> None:  # pragma: no cover - CLI output
    user = db.query(User).filter(User.email == args.email).one_or_none()
    if user is None:
        msg = f"No user found for email {args.email!r}"
        raise ValueError(msg)

    expires_at = None
    if args.expires_in_days is not None:
        if args.expires_in_days <= 0:
            raise ValueError("expires-in-days must be positive")
        expires_at = _now() + timedelta(days=args.expires_in_days)

    raw_key, _ = issue_api_key(db, user, expires_at=expires_at)
    db.commit()
    print(raw_key)


__all__ = [
    "SSOLoginChallenge",
    "TokenPayload",
    "SSO_STATE_COOKIE",
    "authenticate_user",
    "create_access_token",
    "decode_access_token",
    "decode_sso_state",
    "event_actor_from_user",
    "exchange_authorization_code",
    "get_current_user",
    "get_oidc_metadata",
    "hash_api_key",
    "hash_password",
    "issue_api_key",
    "prepare_sso_login",
    "clear_caches",
    "register_cli",
    "require_admin",
    "resolve_sso_user",
    "validate_settings",
    "verify_jwt_via_jwks",
    "verify_password",
]
