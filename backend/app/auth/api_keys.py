"""Helpers for managing API keys."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import ApiKey


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_api_key_token(token: str) -> str:
    """Expose hashing for deterministic fixtures."""

    return _hash_token(token)


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


__all__ = ["get_api_key", "hash_api_key_token", "touch_api_key_usage"]
