"""Auth-related event helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..services.events import EventRecord, record_event
from ..models import User


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
    "cli_action",
    "login_failure",
    "login_success",
    "logout",
    "session_refreshed",
]
