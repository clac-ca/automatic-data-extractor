"""Session management helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import config
from ..models import User, UserSession


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


def issue_session(
    db: Session,
    user: User,
    *,
    settings: config.Settings,
    ip_address: str | None = None,
    user_agent: str | None = None,
    commit: bool = True,
) -> tuple[UserSession, str]:
    """Persist and return a new session plus the raw token."""

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


def hash_session_token(token: str) -> str:
    """Expose token hashing for deterministic testing."""

    return _hash_token(token)


__all__ = [
    "get_session",
    "hash_session_token",
    "issue_session",
    "revoke_session",
    "touch_session",
]
