"""Helpers for normalizing OIDC claims used by SSO callback handling."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def _claim_string(claims: dict[str, Any], key: str) -> str:
    value = claims.get(key)
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_email_candidate(value: str) -> str | None:
    candidate = value.strip()
    if "@" not in candidate:
        return None
    local_part, _, domain = candidate.rpartition("@")
    if not local_part or not domain:
        return None
    return candidate


def is_entra_issuer(issuer: str, claims: dict[str, Any]) -> bool:
    """Return True when issuer host matches Microsoft Entra ID token issuers."""

    del claims
    host = (urlparse(issuer.strip()).hostname or "").lower()
    return (
        host == "sts.windows.net"
        or host == "login.microsoftonline.com"
        or host.startswith("login.microsoftonline.")
        or host.startswith("login.partner.microsoftonline.")
    )


def resolve_subject_key(issuer: str, claims: dict[str, Any]) -> str:
    """Resolve canonical identity key for a validated OIDC token."""

    if is_entra_issuer(issuer, claims):
        tenant_id = _claim_string(claims, "tid")
        object_id = _claim_string(claims, "oid")
        if not tenant_id or not object_id:
            raise ValueError("Entra token is missing tid or oid.")
        return f"{tenant_id}:{object_id}"

    subject = _claim_string(claims, "sub")
    if not subject:
        raise ValueError("ID token subject is missing.")
    return subject


def resolve_email(claims: dict[str, Any]) -> str | None:
    """Resolve a usable email from OIDC claims in priority order."""

    for key in ("email", "preferred_username", "upn"):
        value = _claim_string(claims, key)
        email = _normalize_email_candidate(value)
        if email is not None:
            return email
    return None


def resolve_email_verified_signal(claims: dict[str, Any]) -> bool:
    """Return best-effort verification signal for metadata/auditing purposes."""

    if _coerce_bool(claims.get("email_verified")):
        return True
    if _coerce_bool(claims.get("xms_edov")):
        return True

    verified_primary = claims.get("verified_primary_email")
    if isinstance(verified_primary, str):
        return bool(verified_primary.strip())
    if isinstance(verified_primary, list):
        return any(isinstance(item, str) and bool(item.strip()) for item in verified_primary)
    return _coerce_bool(verified_primary)


__all__ = [
    "is_entra_issuer",
    "resolve_email",
    "resolve_email_verified_signal",
    "resolve_subject_key",
]
