"""Snapshot service helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Snapshot


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _demote_other_published_snapshots(
    db: Session, *, document_type: str, snapshot_id: str
) -> None:
    """Set competing snapshots for the document type back to draft state."""

    statement = select(Snapshot).where(
        Snapshot.document_type == document_type,
        Snapshot.snapshot_id != snapshot_id,
        Snapshot.is_published.is_(True),
    )
    for competing in db.scalars(statement):
        competing.is_published = False
        competing.published_at = None
        db.add(competing)


class SnapshotNotFoundError(Exception):
    """Raised when a snapshot cannot be located."""

    def __init__(self, snapshot_id: str) -> None:
        message = f"Snapshot '{snapshot_id}' was not found"
        super().__init__(message)
        self.snapshot_id = snapshot_id


class PublishedSnapshotNotFoundError(Exception):
    """Raised when a document type has no published snapshot."""

    def __init__(self, document_type: str) -> None:
        message = f"No published snapshot found for document type '{document_type}'"
        super().__init__(message)
        self.document_type = document_type


class SnapshotDocumentTypeMismatchError(Exception):
    """Raised when a snapshot does not belong to the expected document type."""

    def __init__(self, snapshot_id: str, document_type: str, actual_type: str) -> None:
        message = (
            f"Snapshot '{snapshot_id}' belongs to document type '{actual_type}', "
            f"not '{document_type}'"
        )
        super().__init__(message)
        self.snapshot_id = snapshot_id
        self.document_type = document_type
        self.actual_type = actual_type


def list_snapshots(db: Session) -> list[Snapshot]:
    """Return all snapshots ordered by creation time (newest first)."""

    statement = select(Snapshot).order_by(Snapshot.created_at.desc())
    result = db.scalars(statement)
    return list(result)


def get_snapshot(db: Session, snapshot_id: str) -> Snapshot:
    """Return a single snapshot or raise :class:`SnapshotNotFoundError`."""

    snapshot = db.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise SnapshotNotFoundError(snapshot_id)
    return snapshot


def create_snapshot(
    db: Session,
    *,
    document_type: str,
    title: str,
    payload: dict[str, Any] | None = None,
    is_published: bool = False,
) -> Snapshot:
    """Persist and return a new snapshot."""

    snapshot = Snapshot(
        document_type=document_type,
        title=title,
        payload={} if payload is None else payload,
        is_published=is_published,
        published_at=_utcnow_iso() if is_published else None,
    )
    db.add(snapshot)
    if snapshot.is_published:
        _demote_other_published_snapshots(
            db, document_type=snapshot.document_type, snapshot_id=snapshot.snapshot_id
        )
    db.commit()
    db.refresh(snapshot)
    return snapshot


def update_snapshot(
    db: Session,
    snapshot_id: str,
    *,
    title: str | None = None,
    payload: dict[str, Any] | None = None,
    is_published: bool | None = None,
) -> Snapshot:
    """Update and return the snapshot with the given ID."""

    snapshot = get_snapshot(db, snapshot_id)
    if title is not None:
        snapshot.title = title
    if payload is not None:
        snapshot.payload = payload
    if is_published is not None:
        if is_published and not snapshot.is_published:
            snapshot.is_published = True
            snapshot.published_at = _utcnow_iso()
            _demote_other_published_snapshots(
                db,
                document_type=snapshot.document_type,
                snapshot_id=snapshot.snapshot_id,
            )
        elif not is_published and snapshot.is_published:
            snapshot.is_published = False
            snapshot.published_at = None

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete_snapshot(db: Session, snapshot_id: str) -> None:
    """Delete the snapshot with the given ID."""

    snapshot = get_snapshot(db, snapshot_id)
    db.delete(snapshot)
    db.commit()


def get_published_snapshot(db: Session, document_type: str) -> Snapshot:
    """Return the published snapshot for the document type."""

    statement = select(Snapshot).where(
        Snapshot.document_type == document_type,
        Snapshot.is_published.is_(True),
    )
    snapshot = db.scalars(statement).first()
    if snapshot is None:
        raise PublishedSnapshotNotFoundError(document_type)
    return snapshot


def resolve_snapshot(
    db: Session,
    *,
    document_type: str,
    snapshot_id: str | None,
) -> Snapshot:
    """Return the requested snapshot or fall back to the published one."""

    if snapshot_id is None:
        return get_published_snapshot(db, document_type)

    snapshot = get_snapshot(db, snapshot_id)
    if snapshot.document_type != document_type:
        raise SnapshotDocumentTypeMismatchError(
            snapshot_id, document_type, snapshot.document_type
        )
    return snapshot


__all__ = [
    "PublishedSnapshotNotFoundError",
    "SnapshotDocumentTypeMismatchError",
    "SnapshotNotFoundError",
    "create_snapshot",
    "delete_snapshot",
    "get_published_snapshot",
    "get_snapshot",
    "list_snapshots",
    "resolve_snapshot",
    "update_snapshot",
]
