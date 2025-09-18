"""Configuration revision orchestration helpers.

This module centralises the sequencing and activation semantics for
configuration revisions. Service functions enforce the single-active
revision rule per ``document_type`` and provide resolution utilities that
other layers (such as job creation) rely on for deterministic behaviour.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ConfigurationRevision


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_revision_number(db: Session, *, document_type: str) -> int:
    statement = select(func.max(ConfigurationRevision.revision_number)).where(
        ConfigurationRevision.document_type == document_type
    )
    current_max = db.scalar(statement)
    if current_max is None:
        return 1
    return current_max + 1


def _demote_other_active_revisions(
    db: Session, *, document_type: str, configuration_revision_id: str
) -> None:
    """Ensure only one active revision exists per configuration."""

    statement = select(ConfigurationRevision).where(
        ConfigurationRevision.document_type == document_type,
        ConfigurationRevision.configuration_revision_id != configuration_revision_id,
        ConfigurationRevision.is_active.is_(True),
    )
    for competing in db.scalars(statement):
        competing.is_active = False
        competing.activated_at = None
        db.add(competing)


class ConfigurationRevisionNotFoundError(Exception):
    """Raised when a configuration revision cannot be located."""

    def __init__(self, configuration_revision_id: str) -> None:
        message = f"Configuration revision '{configuration_revision_id}' was not found"
        super().__init__(message)
        self.configuration_revision_id = configuration_revision_id


class ActiveConfigurationRevisionNotFoundError(Exception):
    """Raised when a document type lacks an active revision."""

    def __init__(self, document_type: str) -> None:
        message = f"No active configuration revision found for '{document_type}'"
        super().__init__(message)
        self.document_type = document_type


class ConfigurationRevisionMismatchError(Exception):
    """Raised when a revision does not belong to the expected document type."""

    def __init__(
        self, configuration_revision_id: str, document_type: str, actual_document_type: str
    ) -> None:
        message = (
            "Configuration revision "
            f"'{configuration_revision_id}' belongs to document type "
            f"'{actual_document_type}', not '{document_type}'"
        )
        super().__init__(message)
        self.configuration_revision_id = configuration_revision_id
        self.document_type = document_type
        self.actual_document_type = actual_document_type


def list_configuration_revisions(db: Session) -> list[ConfigurationRevision]:
    """Return all revisions ordered by creation time (newest first)."""

    statement = select(ConfigurationRevision).order_by(
        ConfigurationRevision.created_at.desc()
    )
    result = db.scalars(statement)
    return list(result)


def get_configuration_revision(
    db: Session, configuration_revision_id: str
) -> ConfigurationRevision:
    """Return a single revision or raise :class:`ConfigurationRevisionNotFoundError`."""

    revision = db.get(ConfigurationRevision, configuration_revision_id)
    if revision is None:
        raise ConfigurationRevisionNotFoundError(configuration_revision_id)
    return revision


def create_configuration_revision(
    db: Session,
    *,
    document_type: str,
    title: str,
    payload: dict[str, Any] | None = None,
    is_active: bool = False,
) -> ConfigurationRevision:
    """Persist and return a new configuration revision."""

    revision_number = _next_revision_number(db, document_type=document_type)
    revision = ConfigurationRevision(
        document_type=document_type,
        title=title,
        payload={} if payload is None else payload,
        is_active=is_active,
        activated_at=_utcnow_iso() if is_active else None,
        revision_number=revision_number,
    )
    db.add(revision)
    db.flush()
    if revision.is_active:
        _demote_other_active_revisions(
            db,
            document_type=revision.document_type,
            configuration_revision_id=revision.configuration_revision_id,
        )
    db.commit()
    db.refresh(revision)
    return revision


def update_configuration_revision(
    db: Session,
    configuration_revision_id: str,
    *,
    title: str | None = None,
    payload: dict[str, Any] | None = None,
    is_active: bool | None = None,
) -> ConfigurationRevision:
    """Update and return the revision with the given ID."""

    revision = get_configuration_revision(db, configuration_revision_id)
    if title is not None:
        revision.title = title
    if payload is not None:
        revision.payload = payload
    if is_active is not None:
        if is_active and not revision.is_active:
            revision.is_active = True
            revision.activated_at = _utcnow_iso()
            _demote_other_active_revisions(
                db,
                document_type=revision.document_type,
                configuration_revision_id=revision.configuration_revision_id,
            )
        elif not is_active and revision.is_active:
            revision.is_active = False
            revision.activated_at = None

    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


def delete_configuration_revision(db: Session, configuration_revision_id: str) -> None:
    """Delete the revision with the given ID."""

    revision = get_configuration_revision(db, configuration_revision_id)
    db.delete(revision)
    db.commit()


def get_active_configuration_revision(
    db: Session, document_type: str
) -> ConfigurationRevision:
    """Return the active revision for the configuration."""

    statement = select(ConfigurationRevision).where(
        ConfigurationRevision.document_type == document_type,
        ConfigurationRevision.is_active.is_(True),
    )
    revision = db.scalars(statement).first()
    if revision is None:
        raise ActiveConfigurationRevisionNotFoundError(document_type)
    return revision


def resolve_configuration_revision(
    db: Session,
    *,
    document_type: str,
    configuration_revision_id: str | None,
) -> ConfigurationRevision:
    """Return the requested revision or fall back to the active one."""

    if configuration_revision_id is None:
        return get_active_configuration_revision(db, document_type)

    revision = get_configuration_revision(db, configuration_revision_id)
    if revision.document_type != document_type:
        raise ConfigurationRevisionMismatchError(
            configuration_revision_id,
            document_type,
            revision.document_type,
        )
    return revision


__all__ = [
    "ActiveConfigurationRevisionNotFoundError",
    "ConfigurationRevisionMismatchError",
    "ConfigurationRevisionNotFoundError",
    "create_configuration_revision",
    "delete_configuration_revision",
    "get_active_configuration_revision",
    "get_configuration_revision",
    "list_configuration_revisions",
    "resolve_configuration_revision",
    "update_configuration_revision",
]
