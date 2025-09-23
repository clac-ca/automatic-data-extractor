"""Configuration orchestration helpers.

This module centralises the sequencing and activation semantics for
configurations. Service functions enforce the single-active version rule per
``document_type`` and provide resolution utilities that other layers rely on for
deterministic behaviour.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Configuration
from .events import EventRecord, record_event


logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_version(db: Session, *, document_type: str) -> int:
    statement = select(func.max(Configuration.version)).where(
        Configuration.document_type == document_type
    )
    current_max = db.scalar(statement)
    if current_max is None:
        return 1
    return current_max + 1


def _demote_other_active_configurations(
    db: Session, *, document_type: str, configuration_id: str
) -> None:
    """Ensure only one active configuration version exists per document type."""

    statement = select(Configuration).where(
        Configuration.document_type == document_type,
        Configuration.configuration_id != configuration_id,
        Configuration.is_active.is_(True),
    )
    for competing in db.scalars(statement):
        competing.is_active = False
        competing.activated_at = None
        db.add(competing)


def _configuration_event_payload(
    configuration: Configuration,
    *,
    actor_label: str | None = None,
    changed_fields: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "document_type": configuration.document_type,
        "title": configuration.title,
        "version": configuration.version,
        "is_active": configuration.is_active,
    }
    if configuration.activated_at is not None:
        payload["activated_at"] = configuration.activated_at
    if actor_label:
        payload["actor_label"] = actor_label
    if changed_fields:
        payload["changed_fields"] = changed_fields
    return payload


def _record_configuration_event(
    db: Session,
    *,
    configuration: Configuration,
    event_type: str,
    actor_type: str | None,
    actor_id: str | None,
    actor_label: str | None,
    source: str | None,
    request_id: str | None,
    occurred_at: str | None,
    payload: dict[str, Any] | None,
    commit: bool,
) -> None:
    combined_payload = _configuration_event_payload(
        configuration,
        actor_label=actor_label,
    )
    if payload:
        combined_payload.update(payload)

    record = EventRecord(
        event_type=event_type,
        entity_type="configuration",
        entity_id=configuration.configuration_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_label=actor_label,
        source=source,
        request_id=request_id,
        occurred_at=occurred_at,
        payload=combined_payload,
    )

    try:
        record_event(db, record, commit=commit)
    except Exception:
        logger.exception(
            "Failed to record configuration event",
            extra={
                "configuration_id": configuration.configuration_id,
                "event_type": event_type,
                "source": source,
            },
        )


class ConfigurationNotFoundError(Exception):
    """Raised when a configuration cannot be located."""

    def __init__(self, configuration_id: str) -> None:
        message = f"Configuration '{configuration_id}' was not found"
        super().__init__(message)
        self.configuration_id = configuration_id


class ActiveConfigurationNotFoundError(Exception):
    """Raised when a document type lacks an active configuration."""

    def __init__(self, document_type: str) -> None:
        message = f"No active configuration found for '{document_type}'"
        super().__init__(message)
        self.document_type = document_type


class ConfigurationMismatchError(Exception):
    """Raised when a configuration does not belong to the expected document type."""

    def __init__(
        self, configuration_id: str, document_type: str, actual_document_type: str
    ) -> None:
        message = (
            "Configuration "
            f"'{configuration_id}' belongs to document type "
            f"'{actual_document_type}', not '{document_type}'"
        )
        super().__init__(message)
        self.configuration_id = configuration_id
        self.document_type = document_type
        self.actual_document_type = actual_document_type


def list_configurations(db: Session) -> list[Configuration]:
    """Return all configurations ordered by creation time (newest first)."""

    statement = select(Configuration).order_by(Configuration.created_at.desc())
    result = db.scalars(statement)
    return list(result)


def get_configuration(db: Session, configuration_id: str) -> Configuration:
    """Return a configuration or raise :class:`ConfigurationNotFoundError`."""

    configuration = db.get(Configuration, configuration_id)
    if configuration is None:
        raise ConfigurationNotFoundError(configuration_id)
    return configuration


def create_configuration(
    db: Session,
    *,
    document_type: str,
    title: str,
    payload: dict[str, Any] | None = None,
    is_active: bool = False,
    event_actor_type: str | None = None,
    event_actor_id: str | None = None,
    event_actor_label: str | None = None,
    event_source: str | None = None,
    event_request_id: str | None = None,
) -> Configuration:
    """Persist and return a new configuration version."""

    payload_data: dict[str, Any] = {} if payload is None else payload

    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        configuration = Configuration(
            document_type=document_type,
            title=title,
            payload=payload_data,
            is_active=is_active,
            activated_at=_utcnow_iso() if is_active else None,
            version=_next_version(db, document_type=document_type),
        )
        db.add(configuration)
        db.flush()
        if configuration.is_active:
            _demote_other_active_configurations(
                db,
                document_type=configuration.document_type,
                configuration_id=configuration.configuration_id,
            )

        _record_configuration_event(
            db,
            configuration=configuration,
            event_type="configuration.created",
            actor_type=event_actor_type,
            actor_id=event_actor_id,
            actor_label=event_actor_label,
            source=event_source,
            request_id=event_request_id,
            occurred_at=configuration.created_at,
            payload=None,
            commit=False,
        )

        if configuration.is_active:
            _record_configuration_event(
                db,
                configuration=configuration,
                event_type="configuration.activated",
                actor_type=event_actor_type,
                actor_id=event_actor_id,
                actor_label=event_actor_label,
                source=event_source,
                request_id=event_request_id,
                occurred_at=configuration.activated_at,
                payload=None,
                commit=False,
            )
    return configuration


def update_configuration(
    db: Session,
    configuration_id: str,
    *,
    title: str | None = None,
    payload: dict[str, Any] | None = None,
    is_active: bool | None = None,
    event_actor_type: str | None = None,
    event_actor_id: str | None = None,
    event_actor_label: str | None = None,
    event_source: str | None = None,
    event_request_id: str | None = None,
) -> Configuration:
    """Update and return the configuration with the given ID."""

    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        configuration = get_configuration(db, configuration_id)
        changed_fields: list[str] = []
        became_active = False

        if title is not None and title != configuration.title:
            configuration.title = title
            changed_fields.append("title")

        if payload is not None and payload != configuration.payload:
            configuration.payload = payload
            changed_fields.append("payload")

        if is_active is not None:
            if is_active and not configuration.is_active:
                configuration.is_active = True
                configuration.activated_at = _utcnow_iso()
                _demote_other_active_configurations(
                    db,
                    document_type=configuration.document_type,
                    configuration_id=configuration.configuration_id,
                )
                changed_fields.append("is_active")
                became_active = True
            elif not is_active and configuration.is_active:
                configuration.is_active = False
                configuration.activated_at = None
                changed_fields.append("is_active")

        db.add(configuration)
        db.flush()

        if changed_fields:
            _record_configuration_event(
                db,
                configuration=configuration,
                event_type="configuration.updated",
                actor_type=event_actor_type,
                actor_id=event_actor_id,
                actor_label=event_actor_label,
                source=event_source,
                request_id=event_request_id,
                occurred_at=configuration.updated_at,
                payload={"changed_fields": changed_fields},
                commit=False,
            )

        if became_active:
            _record_configuration_event(
                db,
                configuration=configuration,
                event_type="configuration.activated",
                actor_type=event_actor_type,
                actor_id=event_actor_id,
                actor_label=event_actor_label,
                source=event_source,
                request_id=event_request_id,
                occurred_at=configuration.activated_at,
                payload=None,
                commit=False,
            )

    return configuration


def delete_configuration(db: Session, configuration_id: str) -> None:
    """Delete the configuration with the given ID."""

    configuration = get_configuration(db, configuration_id)
    db.delete(configuration)
    db.commit()


def get_active_configuration(db: Session, document_type: str) -> Configuration:
    """Return the active configuration for the supplied document type."""

    statement = select(Configuration).where(
        Configuration.document_type == document_type,
        Configuration.is_active.is_(True),
    )
    configuration = db.scalars(statement).first()
    if configuration is None:
        raise ActiveConfigurationNotFoundError(document_type)
    return configuration


def resolve_configuration(
    db: Session,
    *,
    document_type: str,
    configuration_id: str | None,
) -> Configuration:
    """Return the requested configuration or fall back to the active one."""

    if configuration_id is None:
        return get_active_configuration(db, document_type)

    configuration = get_configuration(db, configuration_id)
    if configuration.document_type != document_type:
        raise ConfigurationMismatchError(
            configuration_id,
            document_type,
            configuration.document_type,
        )
    return configuration


__all__ = [
    "ActiveConfigurationNotFoundError",
    "ConfigurationMismatchError",
    "ConfigurationNotFoundError",
    "create_configuration",
    "delete_configuration",
    "get_active_configuration",
    "get_configuration",
    "list_configurations",
    "resolve_configuration",
    "update_configuration",
]
