"""Consolidated authentication helpers."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from .. import config
from ..models import ApiKey, User, UserSession
from ..services.events import EventRecord, record_event


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


def hash_session_token(token: str) -> str:
    """Expose token hashing for deterministic testing."""

    return _hash_token(token)


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------

def hash_api_key_token(token: str) -> str:
    """Return the deterministic hash for an API key token."""

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


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

def login_success(
    db: Session,
    user: User,
    *,
    mode: str,
    source: str,
    payload: dict[str, Any] | None = None,
    commit: bool = False,
) -> None:
    event_payload = {"mode": mode}
    if payload:
        event_payload.update(payload)
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
        commit=commit,
    )


def login_failure(
    db: Session,
    *,
    email: str,
    mode: str,
    source: str,
    reason: str,
    commit: bool = True,
) -> None:
    event_payload = {"mode": mode, "reason": reason}
    record_event(
        db,
        EventRecord(
            event_type="user.login.failed",
            entity_type="user",
            entity_id=email,
            actor_type="user",
            actor_label=email,
            source=source,
            payload=event_payload,
        ),
        commit=commit,
    )


def logout(
    db: Session,
    user: User,
    *,
    source: str,
    payload: dict[str, Any] | None = None,
    commit: bool = False,
) -> None:
    record_event(
        db,
        EventRecord(
            event_type="user.logout",
            entity_type="user",
            entity_id=user.user_id,
            actor_type="user",
            actor_id=user.user_id,
            actor_label=user.email,
            source=source,
            payload=payload or {},
        ),
        commit=commit,
    )


def session_refreshed(
    db: Session,
    user: User,
    *,
    source: str,
    payload: dict[str, Any] | None = None,
    commit: bool = False,
) -> None:
    event_payload = payload or {}
    record_event(
        db,
        EventRecord(
            event_type="user.session.refreshed",
            entity_type="user",
            entity_id=user.user_id,
            actor_type="user",
            actor_id=user.user_id,
            actor_label=user.email,
            source=source,
            payload=event_payload,
        ),
        commit=commit,
    )


def cli_action(
    db: Session,
    *,
    user: User,
    event_type: str,
    operator_email: str | None,
    payload: dict[str, Any] | None = None,
    commit: bool = False,
) -> None:
    event_payload = {"email": user.email}
    if payload:
        event_payload.update(payload)
    actor_label = operator_email or "cli"
    record_event(
        db,
        EventRecord(
            event_type=event_type,
            entity_type="user",
            entity_id=user.user_id,
            actor_type="system",
            actor_id=operator_email,
            actor_label=actor_label,
            source="cli",
            payload=event_payload,
        ),
        commit=commit,
    )


__all__ = [
    "AuthFailure",
    "AuthResolution",
    "cli_action",
    "get_api_key",
    "get_session",
    "hash_api_key_token",
    "hash_session_token",
    "issue_session",
    "login_failure",
    "login_success",
    "logout",
    "revoke_session",
    "resolve_credentials",
    "session_refreshed",
    "touch_api_key_usage",
    "touch_session",
]
