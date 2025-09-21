"""Authentication helpers, dependencies, and CLI utilities."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import logging
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from http import HTTPStatus
from threading import Lock
from typing import Annotated, Any, Callable, Literal

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    APIKeyCookie,
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db, get_sessionmaker
from ..db_migrations import ensure_schema
from ..models import ApiKey, User, UserRole, UserSession
from .events import EventRecord, record_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Time helpers and token hashing
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_timestamp(value: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith(("Z", "z")):
        candidate = f"{candidate[:-1]}+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_session_token(token: str) -> str:
    """Expose token hashing for deterministic testing."""

    return _hash_token(token)


def hash_api_key_token(token: str) -> str:
    """Return the deterministic hash for an API key token."""

    return _hash_token(token)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def issue_session(
    db: Session,
    user: User,
    *,
    settings: config.Settings,
    ip_address: str | None = None,
    user_agent: str | None = None,
    commit: bool = True,
) -> tuple[UserSession, str]:
    """Persist and return a new session alongside the raw token."""

    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    now = _now()
    expires_at = now + timedelta(minutes=settings.session_ttl_minutes)
    trimmed_agent = (user_agent or "")[:255] or None

    session = UserSession(
        user_id=user.user_id,
        token_hash=token_hash,
        issued_at=_format_timestamp(now),
        expires_at=_format_timestamp(expires_at),
        last_seen_at=_format_timestamp(now),
        last_seen_ip=ip_address,
        last_seen_user_agent=trimmed_agent,
    )
    db.add(session)

    if commit:
        db.commit()
        db.refresh(session)
    else:
        db.flush()

    return session, raw_token


def get_session(db: Session, token: str) -> UserSession | None:
    """Return a valid session for the supplied raw token."""

    if not token:
        return None

    token_hash = _hash_token(token)
    session = (
        db.query(UserSession)
        .filter(UserSession.token_hash == token_hash)
        .one_or_none()
    )
    if session is None:
        return None
    if session.revoked_at is not None:
        return None

    expires_at = _parse_timestamp(session.expires_at)
    if expires_at <= _now():
        return None

    return session


def revoke_session(db: Session, session: UserSession, *, commit: bool = True) -> None:
    """Mark the supplied session as revoked."""

    if session.revoked_at is None:
        session.revoked_at = _format_timestamp(_now())
        if commit:
            db.commit()
        else:
            db.flush()
    elif commit:
        db.commit()


def touch_session(
    db: Session,
    session: UserSession,
    *,
    settings: config.Settings,
    ip_address: str | None = None,
    user_agent: str | None = None,
    commit: bool = True,
) -> UserSession | None:
    """Extend the session expiry and update last seen metadata."""

    if session.revoked_at is not None:
        return None

    current_expiry = _parse_timestamp(session.expires_at)
    now = _now()
    if current_expiry <= now:
        return None

    expires_at = now + timedelta(minutes=settings.session_ttl_minutes)
    session.last_seen_at = _format_timestamp(now)
    session.last_seen_ip = ip_address
    trimmed_agent = (user_agent or "")[:255] or None
    session.last_seen_user_agent = trimmed_agent
    session.expires_at = _format_timestamp(expires_at)

    if commit:
        db.commit()
        db.refresh(session)
    else:
        db.flush()

    return session


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------


def get_api_key(db: Session, token: str) -> ApiKey | None:
    """Return the active API key matching the supplied token."""

    if not token:
        return None

    token_hash = _hash_token(token)
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.token_hash == token_hash)
        .one_or_none()
    )
    if api_key is None:
        return None
    if api_key.revoked_at is not None:
        return None
    return api_key


def touch_api_key_usage(db: Session, api_key: ApiKey, *, commit: bool = True) -> ApiKey:
    """Update API key usage metadata."""

    api_key.last_used_at = _format_timestamp(_now())
    if commit:
        db.commit()
        db.refresh(api_key)
    else:
        db.flush()
    return api_key


# ---------------------------------------------------------------------------
# Auth resolution
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AuthFailure:
    """Structured authentication failure returned by credential resolution."""

    status_code: int
    detail: str
    headers: dict[str, str] | None = None


@dataclass(slots=True)
class AuthResolution:
    """Result of resolving incoming credentials."""

    user: User | None = None
    mode: Literal["session", "api-key"] | None = None
    session: UserSession | None = None
    api_key: ApiKey | None = None
    failure: AuthFailure | None = None


def resolve_credentials(
    db: Session,
    settings: config.Settings,
    *,
    session_token: str | None,
    api_key_token: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuthResolution:
    """Resolve the supplied credentials to a user or an auth failure."""

    pending_commit = False
    session_failure: AuthFailure | None = None

    if session_token:
        session_model = get_session(db, session_token)
        if session_model:
            user = db.get(User, session_model.user_id)
            if user and user.is_active:
                refreshed = touch_session(
                    db,
                    session_model,
                    settings=settings,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    commit=False,
                )
                if refreshed is not None:
                    db.commit()
                    return AuthResolution(
                        user=user,
                        mode="session",
                        session=refreshed,
                    )
                revoke_session(db, session_model, commit=False)
                pending_commit = True
            else:
                revoke_session(db, session_model, commit=False)
                pending_commit = True
        else:
            token_hash = hash_session_token(session_token)
            orphan = (
                db.query(UserSession)
                .filter(UserSession.token_hash == token_hash)
                .one_or_none()
            )
            if orphan is not None:
                revoke_session(db, orphan, commit=False)
                pending_commit = True
        session_failure = AuthFailure(
            status_code=int(HTTPStatus.FORBIDDEN),
            detail="Invalid session token",
        )

    if api_key_token is not None:
        api_key = get_api_key(db, api_key_token)
        if api_key is None:
            if pending_commit:
                db.commit()
            else:
                db.rollback()
            return AuthResolution(
                failure=AuthFailure(
                    status_code=int(HTTPStatus.FORBIDDEN),
                    detail="Invalid API key",
                )
            )

        user = db.get(User, api_key.user_id)
        if user is None or not user.is_active:
            if pending_commit:
                db.commit()
            else:
                db.rollback()
            return AuthResolution(
                failure=AuthFailure(
                    status_code=int(HTTPStatus.FORBIDDEN),
                    detail="Invalid API key",
                )
            )

        updated_api_key = touch_api_key_usage(db, api_key, commit=False)
        db.commit()
        return AuthResolution(
            user=user,
            mode="api-key",
            api_key=updated_api_key,
        )

    if session_failure is not None:
        if pending_commit:
            db.commit()
        else:
            db.rollback()
        return AuthResolution(failure=session_failure)

    db.rollback()
    return AuthResolution(
        failure=AuthFailure(
            status_code=int(HTTPStatus.UNAUTHORIZED),
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Bearer realm="ADE"'},
        )
    )


def complete_login(
    db: Session,
    settings: config.Settings,
    user: User,
    *,
    mode: str,
    source: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    subject: str | None = None,
    include_subject: bool = False,
) -> tuple[UserSession, str]:
    """Issue a session, record telemetry, and persist the login."""

    now_iso = _format_timestamp(_now())
    user.last_login_at = now_iso

    session_model, raw_token = issue_session(
        db,
        user,
        settings=settings,
        ip_address=ip_address,
        user_agent=user_agent,
        commit=False,
    )

    event_payload: dict[str, Any] = {
        "mode": mode,
        "ip": ip_address,
        "user_agent": user_agent,
    }
    if include_subject or subject is not None:
        event_payload["subject"] = subject

    record_event(
        db,
        EventRecord(
            event_type="user.login.succeeded",
            entity_type="user",
            entity_id=user.user_id,
            actor_type="user",
            actor_id=user.user_id,
            actor_label=user.email,
            source=source,
            payload=event_payload,
        ),
        commit=False,
    )

    db.commit()
    db.refresh(user)
    db.refresh(session_model)
    return session_model, raw_token


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_WWW_AUTH_HEADER = 'Bearer realm="ADE"'

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Synthetic admin identity returned when ADE_AUTH_MODES=none.
_OPEN_ACCESS_USER = User(
    user_id="00000000000000000000000000",
    email="open-access@ade.local",
    password_hash=None,
    role=UserRole.ADMIN,
    is_active=True,
)
_OPEN_ACCESS_USER.created_at = "1970-01-01T00:00:00+00:00"
_OPEN_ACCESS_USER.updated_at = "1970-01-01T00:00:00+00:00"


def _client_context(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


async def _session_cookie_value(
    request: Request,
    settings: config.Settings = Depends(config.get_settings),
) -> str | None:
    cookie = APIKeyCookie(name=settings.session_cookie_name, auto_error=False)
    token = await cookie(request)
    if token:
        return token
    return None


def _resolve_api_key_token(
    bearer_credentials: HTTPAuthorizationCredentials | None,
    header_token: str | None,
) -> str | None:
    if bearer_credentials and bearer_credentials.credentials:
        return bearer_credentials.credentials
    if header_token:
        return header_token
    return None


@dataclass(slots=True)
class AuthenticatedIdentity:
    """Resolved authentication details for the current request."""

    user: User
    mode: str
    session: UserSession | None = None
    api_key: ApiKey | None = None
    session_id: str | None = None
    api_key_id: str | None = None
    subject: str | None = None


def get_authenticated_identity(
    request: Request,
    db: Session = Depends(get_db),
    settings: config.Settings = Depends(config.get_settings),
    session_token: str | None = Depends(_session_cookie_value),
    bearer_credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    header_token: str | None = Depends(_api_key_header),
) -> AuthenticatedIdentity:
    if settings.auth_disabled:
        return AuthenticatedIdentity(user=_OPEN_ACCESS_USER, mode="none")

    ip_address, user_agent = _client_context(request)
    api_key_token = _resolve_api_key_token(bearer_credentials, header_token)
    resolution = resolve_credentials(
        db,
        settings,
        session_token=session_token,
        api_key_token=api_key_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if resolution.user is not None:
        mode = resolution.mode
        if mode is None:
            raise RuntimeError("Resolved authenticated user without an auth mode")
        session_model: UserSession | None = None
        api_key_model: ApiKey | None = None
        session_id: str | None = None
        api_key_id: str | None = None
        if mode == "session" and resolution.session is not None:
            session_model = resolution.session
            session_id = session_model.session_id
        elif mode == "api-key" and resolution.api_key is not None:
            api_key_model = resolution.api_key
            api_key_id = api_key_model.api_key_id

        subject: str | None = resolution.user.sso_subject

        return AuthenticatedIdentity(
            user=resolution.user,
            mode=mode,
            session=session_model,
            api_key=api_key_model,
            session_id=session_id,
            api_key_id=api_key_id,
            subject=subject,
        )

    failure = resolution.failure
    if failure is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": _WWW_AUTH_HEADER},
        )

    raise HTTPException(
        failure.status_code,
        detail=failure.detail,
        headers=failure.headers,
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: config.Settings = Depends(config.get_settings),
    session_token: str | None = Depends(_session_cookie_value),
    bearer_credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    header_token: str | None = Depends(_api_key_header),
) -> User:
    identity = get_authenticated_identity(
        request,
        db=db,
        settings=settings,
        session_token=session_token,
        bearer_credentials=bearer_credentials,
        header_token=header_token,
    )
    return identity.user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Administrator privileges required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


def validate_settings(settings: config.Settings) -> None:
    """Raise ``RuntimeError`` when authentication settings are invalid."""

    try:
        modes = settings.auth_mode_sequence
    except ValueError as exc:  # pragma: no cover - defensive
        raise RuntimeError(str(exc)) from exc

    sessions_active = modes != ("none",)
    if sessions_active:
        if settings.session_cookie_same_site == "none" and not settings.session_cookie_secure:
            raise RuntimeError(
                "ADE_SESSION_COOKIE_SECURE must be enabled when SameSite is set to 'none'"
            )

    if "sso" in modes:
        required = {
            "ADE_SSO_CLIENT_ID": settings.sso_client_id,
            "ADE_SSO_CLIENT_SECRET": settings.sso_client_secret,
            "ADE_SSO_ISSUER": settings.sso_issuer,
            "ADE_SSO_REDIRECT_URL": settings.sso_redirect_url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            joined = ", ".join(sorted(missing))
            raise RuntimeError(f"Missing SSO configuration values: {joined}")

    if settings.admin_email_allowlist_enabled and not settings.admin_allowlist:
        raise RuntimeError(
            "ADE_ADMIN_EMAIL_ALLOWLIST must list at least one address when the allowlist is enabled"
        )


# ---------------------------------------------------------------------------
# SSO helpers
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    value: Any
    expires_at: datetime


@dataclass
class OIDCMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


class SSOConfigurationError(RuntimeError):
    """Raised when SSO settings are incomplete."""


class SSOExchangeError(RuntimeError):
    """Raised when an SSO authentication attempt fails."""


_DISCOVERY_CACHE: dict[str, _CacheEntry] = {}
_JWKS_CACHE: dict[str, _CacheEntry] = {}
_CACHE_LOCK = Lock()

_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def _assert_sso_enabled(settings: config.Settings) -> None:
    if "sso" not in settings.auth_mode_sequence:
        raise SSOConfigurationError("SSO mode is not enabled")

    required = {
        "ADE_SSO_CLIENT_ID": settings.sso_client_id,
        "ADE_SSO_CLIENT_SECRET": settings.sso_client_secret,
        "ADE_SSO_ISSUER": settings.sso_issuer,
        "ADE_SSO_REDIRECT_URL": settings.sso_redirect_url,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        joined = ", ".join(missing)
        raise SSOConfigurationError(f"Missing configuration: {joined}")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _get_cached(cache: dict[str, _CacheEntry], key: str) -> Any | None:
    entry = cache.get(key)
    if entry is None:
        return None
    if entry.expires_at <= _now_utc():
        return None
    return entry.value


def _set_cached(cache: dict[str, _CacheEntry], key: str, value: Any, ttl_seconds: int) -> None:
    cache[key] = _CacheEntry(value=value, expires_at=_now_utc() + timedelta(seconds=ttl_seconds))


def clear_caches() -> None:
    """Clear cached discovery documents and JWKS payloads."""

    with _CACHE_LOCK:
        _DISCOVERY_CACHE.clear()
        _JWKS_CACHE.clear()


def _discovery_url(issuer: str) -> str:
    base = issuer.rstrip("/")
    return f"{base}/.well-known/openid-configuration"


def _fetch_discovery(settings: config.Settings) -> OIDCMetadata:
    assert settings.sso_issuer is not None
    cache_key = settings.sso_issuer
    with _CACHE_LOCK:
        cached = _get_cached(_DISCOVERY_CACHE, cache_key)
        if cached is not None:
            return cached

    url = _discovery_url(settings.sso_issuer)
    try:
        response = httpx.get(url, timeout=10.0)
    except httpx.HTTPError as exc:  # pragma: no cover - defensive
        raise SSOExchangeError("Failed to load OIDC discovery document") from exc

    if response.status_code >= 400:
        raise SSOExchangeError("Failed to load OIDC discovery document")

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise SSOExchangeError("Failed to load OIDC discovery document") from exc

    try:
        metadata = OIDCMetadata(
            issuer=payload["issuer"],
            authorization_endpoint=payload["authorization_endpoint"],
            token_endpoint=payload["token_endpoint"],
            jwks_uri=payload["jwks_uri"],
        )
    except KeyError as exc:  # pragma: no cover - defensive
        raise SSOExchangeError("OIDC discovery document missing fields") from exc

    with _CACHE_LOCK:
        _set_cached(_DISCOVERY_CACHE, cache_key, metadata, settings.sso_cache_ttl_seconds)
    return metadata


def _fetch_jwks(settings: config.Settings, jwks_uri: str) -> dict[str, Any]:
    cache_key = jwks_uri
    with _CACHE_LOCK:
        cached = _get_cached(_JWKS_CACHE, cache_key)
        if cached is not None:
            return cached

    try:
        response = httpx.get(jwks_uri, timeout=10.0)
    except httpx.HTTPError as exc:  # pragma: no cover - defensive
        raise SSOExchangeError("Failed to load JWKS") from exc

    if response.status_code >= 400:
        raise SSOExchangeError("Failed to load JWKS")

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise SSOExchangeError("Failed to load JWKS") from exc

    if "keys" not in payload:
        raise SSOExchangeError("JWKS response missing keys array")

    with _CACHE_LOCK:
        _set_cached(_JWKS_CACHE, cache_key, payload, settings.sso_cache_ttl_seconds)
    return payload


def _build_state_token(settings: config.Settings) -> tuple[str, dict[str, Any]]:
    assert settings.sso_client_secret is not None
    state_payload = {
        "nonce": secrets.token_urlsafe(16),
        "exp": int((_now_utc() + timedelta(minutes=5)).timestamp()),
    }
    body = json.dumps(state_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(settings.sso_client_secret.encode("utf-8"), body, hashlib.sha256).digest()
    packed = f"{_b64url_encode(body)}.{_b64url_encode(signature)}"
    return packed, state_payload


def _verify_state_token(settings: config.Settings, token: str) -> dict[str, Any]:
    assert settings.sso_client_secret is not None
    key_bytes = settings.sso_client_secret.encode("utf-8")
    try:
        if "." in token:
            body_b64, signature_b64 = token.split(".", 1)
            if not body_b64 or not signature_b64:
                raise ValueError("Missing state token components")
            body = _b64url_decode(body_b64)
            signature = _b64url_decode(signature_b64)
        else:
            decoded = _b64url_decode(token)
            if len(decoded) < 33 or decoded[-33] != 0x2E:
                raise ValueError("Invalid legacy state token format")
            body = decoded[:-33]
            signature = decoded[-32:]
    except (ValueError, binascii.Error) as exc:
        raise SSOExchangeError("Invalid state token") from exc

    expected = hmac.new(key_bytes, body, hashlib.sha256).digest()
    if not compare_digest(expected, signature):
        raise SSOExchangeError("Invalid state token")

    payload = json.loads(body.decode("utf-8"))
    if payload.get("exp", 0) < int(_now_utc().timestamp()):
        raise SSOExchangeError("State token expired")
    return payload


def _select_jwk(jwks: dict[str, Any], kid: str | None) -> dict[str, Any]:
    keys = jwks.get("keys", [])
    for entry in keys:
        if kid is None or entry.get("kid") == kid:
            return entry
    raise SSOExchangeError("Signing key not found for ID token")


def _decode_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise SSOExchangeError("ID token format invalid") from exc

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (json.JSONDecodeError, binascii.Error) as exc:
        raise SSOExchangeError("ID token format invalid") from exc

    try:
        signature = _b64url_decode(signature_b64)
    except binascii.Error as exc:
        raise SSOExchangeError("ID token format invalid") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    return header, payload, signature, signing_input


def _verify_rs256(jwk: dict[str, Any], signing_input: bytes, signature: bytes) -> None:
    try:
        n_bytes = _b64url_decode(jwk["n"])
        e_bytes = _b64url_decode(jwk["e"])
    except KeyError as exc:
        raise SSOExchangeError("JWKS entry missing RSA parameters") from exc

    n_int = int.from_bytes(n_bytes, "big")
    e_int = int.from_bytes(e_bytes, "big")
    if n_int <= 0 or e_int <= 0:
        raise SSOExchangeError("Invalid RSA key")

    key_size = (n_int.bit_length() + 7) // 8
    if len(signature) != key_size:
        raise SSOExchangeError("ID token validation failed")

    sig_int = int.from_bytes(signature, "big")
    decrypted = pow(sig_int, e_int, n_int)
    em = decrypted.to_bytes(key_size, "big")
    if not em.startswith(b"\x00\x01"):
        raise SSOExchangeError("ID token validation failed")

    try:
        separator = em.index(b"\x00", 2)
    except ValueError as exc:
        raise SSOExchangeError("ID token validation failed") from exc

    padding = em[2:separator]
    if padding != b"\xff" * len(padding):
        raise SSOExchangeError("ID token validation failed")

    digest_info = em[separator + 1 :]
    expected = _SHA256_PREFIX + hashlib.sha256(signing_input).digest()
    if not compare_digest(digest_info, expected):
        raise SSOExchangeError("ID token validation failed")


def _verify_hs256(
    jwk: dict[str, Any],
    signing_input: bytes,
    signature: bytes,
    settings: config.Settings,
) -> None:
    secret = jwk.get("k")
    if secret is not None:
        key_bytes = _b64url_decode(secret)
    elif settings.sso_client_secret:
        key_bytes = settings.sso_client_secret.encode("utf-8")
    else:
        raise SSOExchangeError("Missing shared secret for HS256 tokens")

    expected = hmac.new(key_bytes, signing_input, hashlib.sha256).digest()
    if not compare_digest(expected, signature):
        raise SSOExchangeError("ID token validation failed")


def _verify_signature(
    header: dict[str, Any],
    jwk: dict[str, Any],
    signing_input: bytes,
    signature: bytes,
    settings: config.Settings,
) -> None:
    algorithm = header.get("alg")
    if algorithm == "RS256":
        _verify_rs256(jwk, signing_input, signature)
    elif algorithm == "HS256":
        _verify_hs256(jwk, signing_input, signature, settings)
    else:
        raise SSOExchangeError(f"Unsupported ID token algorithm: {algorithm}")


def _decode_id_token(
    id_token: str,
    *,
    metadata: OIDCMetadata,
    jwks: dict[str, Any],
    settings: config.Settings,
    expected_nonce: str | None,
) -> dict[str, Any]:
    header, payload, signature, signing_input = _decode_jwt(id_token)
    kid = header.get("kid")
    jwk = _select_jwk(jwks, kid)
    _verify_signature(header, jwk, signing_input, signature, settings)

    audience = settings.sso_audience or settings.sso_client_id
    if audience is None:
        raise SSOExchangeError("Missing audience configuration")

    if payload.get("iss") != metadata.issuer:
        raise SSOExchangeError("ID token issuer mismatch")

    aud_claim = payload.get("aud")
    if isinstance(aud_claim, str):
        audiences = [aud_claim]
    elif isinstance(aud_claim, list):
        audiences = [str(item) for item in aud_claim]
    else:
        raise SSOExchangeError("ID token missing audience")
    if audience not in audiences:
        raise SSOExchangeError("ID token audience mismatch")

    try:
        exp = int(payload["exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SSOExchangeError("ID token missing expiry") from exc
    if datetime.fromtimestamp(exp, tz=timezone.utc) <= _now_utc():
        raise SSOExchangeError("ID token expired")

    if expected_nonce is not None and payload.get("nonce") != expected_nonce:
        raise SSOExchangeError("Unexpected nonce in ID token")

    return payload


def build_authorization_url(settings: config.Settings) -> str:
    """Return the authorisation URL for the configured provider."""

    _assert_sso_enabled(settings)
    metadata = _fetch_discovery(settings)
    state_token, payload = _build_state_token(settings)
    params = {
        "response_type": "code",
        "client_id": settings.sso_client_id,
        "redirect_uri": settings.sso_redirect_url,
        "scope": settings.sso_scopes,
        "state": state_token,
        "nonce": payload["nonce"],
    }
    url = httpx.URL(metadata.authorization_endpoint)
    return str(url.copy_merge_params(params))


def _resolve_user(db: Session, settings: config.Settings, claims: dict[str, Any]) -> User:
    issuer = claims.get("iss")
    subject = claims.get("sub")
    if not issuer or not subject:
        raise SSOExchangeError("ID token missing issuer or subject")

    statement = select(User).where(
        User.sso_provider == issuer,
        User.sso_subject == subject,
    )
    user = db.execute(statement).scalar_one_or_none()

    if user is None:
        if not settings.sso_auto_provision:
            raise SSOExchangeError("SSO user is not provisioned")
        email = (claims.get("email") or "").strip().lower()
        if not email:
            raise SSOExchangeError("Email claim required for auto provisioning")
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing is None:
            user = User(
                email=email,
                password_hash=None,
                role=UserRole.VIEWER,
                is_active=True,
                sso_provider=issuer,
                sso_subject=subject,
            )
            db.add(user)
        else:
            user = existing
            user.sso_provider = issuer
            user.sso_subject = subject
        db.flush()
    else:
        if not user.is_active:
            raise SSOExchangeError("User account is deactivated")

    return user


def exchange_code(
    settings: config.Settings,
    *,
    code: str,
    state: str,
    db: Session,
) -> tuple[User, dict[str, Any]]:
    """Complete the OIDC code exchange and return the authenticated user."""

    _assert_sso_enabled(settings)
    metadata = _fetch_discovery(settings)
    state_payload = _verify_state_token(settings, state)

    assert settings.sso_client_id is not None
    assert settings.sso_client_secret is not None
    assert settings.sso_redirect_url is not None

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.sso_redirect_url,
        "client_id": settings.sso_client_id,
        "client_secret": settings.sso_client_secret,
    }
    try:
        response = httpx.post(metadata.token_endpoint, data=data, timeout=10.0)
    except httpx.HTTPError as exc:  # pragma: no cover - defensive
        raise SSOExchangeError("Failed to exchange authorisation code") from exc

    if response.status_code >= 400:
        raise SSOExchangeError("Failed to exchange authorisation code")

    try:
        tokens = response.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise SSOExchangeError("Failed to exchange authorisation code") from exc

    id_token = tokens.get("id_token")
    if not id_token:
        raise SSOExchangeError("Token response missing id_token")

    jwks = _fetch_jwks(settings, metadata.jwks_uri)
    claims = _decode_id_token(
        id_token,
        metadata=metadata,
        jwks=jwks,
        settings=settings,
        expected_nonce=state_payload.get("nonce"),
    )
    user = _resolve_user(db, settings, claims)
    return user, claims


def verify_bearer_token(
    settings: config.Settings,
    *,
    token: str,
    db: Session,
) -> tuple[User, dict[str, Any]]:
    """Validate an ID token supplied via ``Authorization: Bearer``."""

    _assert_sso_enabled(settings)
    metadata = _fetch_discovery(settings)
    jwks = _fetch_jwks(settings, metadata.jwks_uri)
    claims = _decode_id_token(
        token,
        metadata=metadata,
        jwks=jwks,
        settings=settings,
        expected_nonce=None,
    )
    user = _resolve_user(db, settings, claims)
    return user, claims


# ---------------------------------------------------------------------------
# CLI utilities
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage ADE user accounts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _add_operator_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--operator-email",
            help="Email address recorded as the actor for emitted events",
        )

    create = subparsers.add_parser("create-user", help="Create a new ADE user")
    create.add_argument("email", help="Email address of the user")
    create.add_argument("--password", help="Password for HTTP Basic authentication")
    create.add_argument(
        "--role",
        choices=[role.value for role in UserRole],
        default=UserRole.VIEWER.value,
        help="Role assigned to the user",
    )
    create.add_argument("--sso-provider", help="OIDC provider identifier")
    create.add_argument("--sso-subject", help="OIDC subject identifier")
    create.add_argument("--inactive", action="store_true", help="Create the account in a disabled state")

    _add_operator_argument(create)

    reset = subparsers.add_parser("reset-password", help="Set a new password for an existing user")
    reset.add_argument("email", help="Email address of the user")
    reset.add_argument("--password", required=True, help="New password value")

    _add_operator_argument(reset)

    deactivate = subparsers.add_parser("deactivate", help="Deactivate a user account")
    deactivate.add_argument("email", help="Email address of the user")

    _add_operator_argument(deactivate)

    promote = subparsers.add_parser("promote", help="Grant administrator privileges to a user")
    promote.add_argument("email", help="Email address of the user")

    _add_operator_argument(promote)

    list_users = subparsers.add_parser("list-users", help="Display all user accounts")
    list_users.add_argument("--show-inactive", action="store_true", help="Include deactivated accounts")

    return parser


def _ensure_schema() -> None:
    ensure_schema()


def _normalise_email(email: str) -> str:
    candidate = email.strip().lower()
    if not candidate:
        raise ValueError("Email address cannot be empty")
    return candidate


def _load_user(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.execute(statement).scalar_one_or_none()


def _enforce_admin_allowlist(settings: config.Settings, email: str) -> None:
    if not settings.admin_email_allowlist_enabled:
        return
    if email not in settings.admin_allowlist:
        raise ValueError(
            "Email address is not permitted to hold administrator privileges"
        )


def _create_user(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    email = _normalise_email(args.email)
    if _load_user(db, email) is not None:
        raise ValueError("User already exists")

    role = UserRole(args.role)
    if role == UserRole.ADMIN:
        _enforce_admin_allowlist(settings, email)

    password_hash: str | None = None
    if args.password:
        password_hash = hash_password(args.password)
    elif not args.sso_subject:
        raise ValueError("Password or --sso-subject is required")

    user = User(
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=not args.inactive,
        sso_provider=args.sso_provider,
        sso_subject=args.sso_subject,
    )
    db.add(user)
    db.flush()

    operator_email = args.operator_email
    actor_label = operator_email or "cli"
    record_event(
        db,
        EventRecord(
            event_type="user.created",
            entity_type="user",
            entity_id=user.user_id,
            actor_type="system",
            actor_id=operator_email,
            actor_label=actor_label,
            source="cli",
            payload={"email": user.email, "role": role.value},
        ),
        commit=False,
    )
    db.commit()
    print(f"Created user {user.email} ({user.user_id})")


def _reset_password(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    email = _normalise_email(args.email)
    user = _load_user(db, email)
    if user is None:
        raise ValueError("User not found")

    user.password_hash = hash_password(args.password)
    db.flush()
    operator_email = args.operator_email
    actor_label = operator_email or "cli"
    record_event(
        db,
        EventRecord(
            event_type="user.password.reset",
            entity_type="user",
            entity_id=user.user_id,
            actor_type="system",
            actor_id=operator_email,
            actor_label=actor_label,
            source="cli",
            payload={"email": user.email},
        ),
        commit=False,
    )
    db.commit()
    print(f"Password reset for {user.email}")


def _deactivate_user(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    email = _normalise_email(args.email)
    user = _load_user(db, email)
    if user is None:
        raise ValueError("User not found")

    user.is_active = False
    db.flush()
    operator_email = args.operator_email
    actor_label = operator_email or "cli"
    record_event(
        db,
        EventRecord(
            event_type="user.deactivated",
            entity_type="user",
            entity_id=user.user_id,
            actor_type="system",
            actor_id=operator_email,
            actor_label=actor_label,
            source="cli",
            payload={"email": user.email},
        ),
        commit=False,
    )
    db.commit()
    print(f"Deactivated {user.email}")


def _promote_user(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    email = _normalise_email(args.email)
    user = _load_user(db, email)
    if user is None:
        raise ValueError("User not found")

    _enforce_admin_allowlist(settings, email)
    user.role = UserRole.ADMIN
    db.flush()
    operator_email = args.operator_email
    actor_label = operator_email or "cli"
    record_event(
        db,
        EventRecord(
            event_type="user.promoted",
            entity_type="user",
            entity_id=user.user_id,
            actor_type="system",
            actor_id=operator_email,
            actor_label=actor_label,
            source="cli",
            payload={"email": user.email, "role": UserRole.ADMIN.value},
        ),
        commit=False,
    )
    db.commit()
    print(f"Promoted {user.email} to administrator")


def _list_users(db: Session, settings: config.Settings, args: argparse.Namespace) -> None:
    statement = select(User).order_by(User.email)
    rows = db.execute(statement).scalars().all()
    for user in rows:
        if not args.show_inactive and not user.is_active:
            continue
        status_label = "active" if user.is_active else "inactive"
        sso_info = ""
        if user.sso_provider and user.sso_subject:
            sso_info = f" sso={user.sso_provider}:{user.sso_subject}"
        print(f"{user.email} ({user.role.value}, {status_label}){sso_info}")


def _with_session(func: Callable[[Session, config.Settings, argparse.Namespace], None], args: argparse.Namespace) -> None:
    settings = config.get_settings()
    session_factory = get_sessionmaker()
    with session_factory() as db:
        func(db, settings, args)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        _ensure_schema()
        command_map: dict[str, Callable[[Session, config.Settings, argparse.Namespace], None]] = {
            "create-user": _create_user,
            "reset-password": _reset_password,
            "deactivate": _deactivate_user,
            "promote": _promote_user,
            "list-users": _list_users,
        }
        handler = command_map[args.command]
        _with_session(handler, args)
        return 0
    except ValueError as exc:
        logger.error(str(exc))
        return 1
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("User management command failed")
        return 1


__all__ = [
    "AdminUser",
    "AuthenticatedIdentity",
    "AuthFailure",
    "AuthResolution",
    "CurrentUser",
    "OIDCMetadata",
    "SSOConfigurationError",
    "SSOExchangeError",
    "clear_caches",
    "complete_login",
    "exchange_code",
    "get_api_key",
    "get_authenticated_identity",
    "get_current_user",
    "get_session",
    "hash_api_key_token",
    "hash_password",
    "hash_session_token",
    "issue_session",
    "main",
    "require_admin",
    "resolve_credentials",
    "revoke_session",
    "touch_api_key_usage",
    "touch_session",
    "validate_settings",
    "verify_bearer_token",
    "verify_password",
]


if __name__ == "__main__":
    sys.exit(main())
