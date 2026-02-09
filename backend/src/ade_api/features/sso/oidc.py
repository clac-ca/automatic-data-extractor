"""OIDC discovery, token exchange, and ID token validation helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

DISCOVERY_TTL = timedelta(minutes=15)

_discovery_cache: dict[str, tuple[datetime, OidcMetadata]] = {}
_jwks_clients: dict[str, PyJWKClient] = {}


class OidcDiscoveryError(RuntimeError):
    """Raised when OIDC discovery fails."""


class OidcTokenExchangeError(RuntimeError):
    """Raised when token exchange fails."""


class OidcTokenValidationError(RuntimeError):
    """Raised when ID token validation fails."""


class OidcJwksError(RuntimeError):
    """Raised when JWKS/key resolution fails."""


@dataclass(frozen=True, slots=True)
class OidcMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _get_jwks_client(jwks_uri: str) -> PyJWKClient:
    client = _jwks_clients.get(jwks_uri)
    if client is None:
        client = PyJWKClient(jwks_uri, cache_keys=True, cache_jwk_set=True, lifespan=300)
        _jwks_clients[jwks_uri] = client
    return client


def _extract_unverified_claims(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_iss": False,
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
    except Exception:
        return {}
    return {
        "iss": claims.get("iss"),
        "aud": claims.get("aud"),
        "azp": claims.get("azp"),
        "nonce": claims.get("nonce"),
        "iat": claims.get("iat"),
        "exp": claims.get("exp"),
    }


def _extract_unverified_header(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return {}
    return {"alg": header.get("alg"), "kid": header.get("kid"), "typ": header.get("typ")}


def discover_metadata(issuer: str, client: httpx.Client) -> OidcMetadata:
    normalized = issuer.rstrip("/")
    cached = _discovery_cache.get(normalized)
    if cached and cached[0] > _now():
        return cached[1]

    url = f"{normalized}/.well-known/openid-configuration"
    try:
        response = client.get(url, timeout=10.0)
    except httpx.HTTPError as exc:
        logger.warning("sso.oidc.discovery.failed", extra={"issuer": normalized})
        raise OidcDiscoveryError("Discovery request failed") from exc

    if response.status_code != 200:
        logger.warning(
            "sso.oidc.discovery.status",
            extra={"issuer": normalized, "status_code": response.status_code},
        )
        raise OidcDiscoveryError("Discovery response was not successful")

    try:
        payload = response.json()
    except ValueError as exc:
        raise OidcDiscoveryError("Discovery response was not JSON") from exc

    auth_endpoint = payload.get("authorization_endpoint")
    token_endpoint = payload.get("token_endpoint")
    jwks_uri = payload.get("jwks_uri")
    discovered_issuer = payload.get("issuer") or normalized

    if not auth_endpoint or not token_endpoint or not jwks_uri:
        raise OidcDiscoveryError("Discovery response missing required endpoints")

    if discovered_issuer.rstrip("/") != normalized:
        raise OidcDiscoveryError("Discovery issuer mismatch")

    metadata = OidcMetadata(
        issuer=normalized,
        authorization_endpoint=str(auth_endpoint),
        token_endpoint=str(token_endpoint),
        jwks_uri=str(jwks_uri),
    )
    _discovery_cache[normalized] = (_now() + DISCOVERY_TTL, metadata)
    return metadata


def exchange_code(
    *,
    token_endpoint: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    client: httpx.Client,
) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    try:
        response = client.post(
            token_endpoint,
            data=data,
            auth=(client_id, client_secret),
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise OidcTokenExchangeError("Token exchange request failed") from exc

    if response.status_code != 200:
        raise OidcTokenExchangeError("Token exchange failed")

    try:
        payload = response.json()
    except ValueError as exc:
        raise OidcTokenExchangeError("Token exchange returned invalid JSON") from exc

    if "id_token" not in payload:
        raise OidcTokenExchangeError("Token response missing id_token")

    return payload


def validate_id_token(
    *,
    token: str,
    issuer: str,
    client_id: str,
    nonce: str,
    jwks_uri: str,
    now: datetime | None = None,
    clock_skew_seconds: int = 120,
) -> dict[str, Any]:
    timestamp = now or _now()
    jwk_client = _get_jwks_client(jwks_uri)
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
    except Exception as exc:
        raise OidcJwksError("Unable to resolve signing key") from exc

    header = _extract_unverified_header(token)
    alg = header.get("alg") if isinstance(header.get("alg"), str) else None
    if alg is None:
        raise OidcTokenValidationError("Token algorithm missing")

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience=client_id,
            issuer=issuer,
            leeway=clock_skew_seconds,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except Exception as exc:
        logger.warning(
            "sso.oidc.token.invalid",
            extra={
                "issuer": issuer,
                "client_id": client_id,
                "claims": _extract_unverified_claims(token),
                "header": header,
                "error": str(exc),
            },
        )
        raise OidcTokenValidationError("Token validation failed") from exc

    if claims.get("nonce") != nonce:
        raise OidcTokenValidationError("Nonce mismatch")

    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1:
        if claims.get("azp") != client_id:
            raise OidcTokenValidationError("Authorized party mismatch")

    issued_at = claims.get("iat")
    if isinstance(issued_at, (int, float)):
        iat_dt = datetime.fromtimestamp(int(issued_at), tz=UTC)
        if iat_dt > timestamp + timedelta(seconds=clock_skew_seconds):
            raise OidcTokenValidationError("Token issued in the future")

    return claims


__all__ = [
    "DISCOVERY_TTL",
    "OidcDiscoveryError",
    "OidcMetadata",
    "OidcJwksError",
    "OidcTokenExchangeError",
    "OidcTokenValidationError",
    "discover_metadata",
    "exchange_code",
    "validate_id_token",
]
