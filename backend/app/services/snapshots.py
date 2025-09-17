"""Snapshot service helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Snapshot


class SnapshotNotFoundError(Exception):
    """Raised when a snapshot cannot be located."""

    def __init__(self, snapshot_id: str) -> None:
        message = f"Snapshot '{snapshot_id}' was not found"
        super().__init__(message)
        self.snapshot_id = snapshot_id


def list_snapshots(db: Session) -> list[Snapshot]:
    """Return all snapshots ordered by creation time (newest first)."""

    statement = select(Snapshot).order_by(Snapshot.created_at.desc())
    result = db.scalars(statement)
    return result.all()


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
    )
    db.add(snapshot)
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
        snapshot.is_published = is_published

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete_snapshot(db: Session, snapshot_id: str) -> None:
    """Delete the snapshot with the given ID."""

    snapshot = get_snapshot(db, snapshot_id)
    db.delete(snapshot)
    db.commit()
