"""OIDC helpers for ADE single sign-on."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from threading import Lock
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import User, UserRole


class SSOConfigurationError(RuntimeError):
    """Raised when SSO settings are incomplete."""


class SSOExchangeError(RuntimeError):
    """Raised when an SSO authentication attempt fails."""


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


_DISCOVERY_CACHE: dict[str, _CacheEntry] = {}
_JWKS_CACHE: dict[str, _CacheEntry] = {}
_CACHE_LOCK = Lock()

_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def _now() -> datetime:
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
    if entry.expires_at <= _now():
        return None
    return entry.value


def _set_cached(cache: dict[str, _CacheEntry], key: str, value: Any, ttl_seconds: int) -> None:
    cache[key] = _CacheEntry(value=value, expires_at=_now() + timedelta(seconds=ttl_seconds))


def clear_caches() -> None:
    """Clear cached discovery documents and JWKS payloads."""

    with _CACHE_LOCK:
        _DISCOVERY_CACHE.clear()
        _JWKS_CACHE.clear()


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
        "exp": int((_now() + timedelta(minutes=5)).timestamp()),
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
    except (ValueError, binascii.Error) as exc:  # pragma: no cover - defensive
        raise SSOExchangeError("Invalid state token") from exc

    expected = hmac.new(key_bytes, body, hashlib.sha256).digest()
    if not compare_digest(signature, expected):
        raise SSOExchangeError("Invalid state token signature")

    payload = json.loads(body.decode("utf-8"))
    if payload.get("exp", 0) < int(_now().timestamp()):
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
    if datetime.fromtimestamp(exp, tz=timezone.utc) <= _now():
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


__all__ = [
    "SSOConfigurationError",
    "SSOExchangeError",
    "OIDCMetadata",
    "clear_caches",
    "build_authorization_url",
    "exchange_code",
    "verify_bearer_token",
]
