"""HTTP endpoints for snapshot resources."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Snapshot
from ..schemas import SnapshotCreate, SnapshotResponse, SnapshotUpdate
from ..services.snapshots import (
    SnapshotNotFoundError,
    create_snapshot,
    delete_snapshot,
    get_snapshot,
    list_snapshots,
    update_snapshot,
)

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


def _to_response(snapshot: Snapshot) -> SnapshotResponse:
    """Convert ORM objects to response models."""

    return SnapshotResponse.model_validate(snapshot)


@router.post("", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot_endpoint(
    payload: SnapshotCreate,
    db: Session = Depends(get_db),
) -> SnapshotResponse:
    """Create a new snapshot."""

    snapshot = create_snapshot(
        db,
        document_type=payload.document_type,
        title=payload.title,
        payload=payload.payload,
        is_published=payload.is_published,
    )
    return _to_response(snapshot)


@router.get("", response_model=list[SnapshotResponse])
def list_snapshots_endpoint(db: Session = Depends(get_db)) -> list[SnapshotResponse]:
    """Return all snapshots."""

    snapshots = list_snapshots(db)
    return [_to_response(snapshot) for snapshot in snapshots]


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot_endpoint(snapshot_id: str, db: Session = Depends(get_db)) -> SnapshotResponse:
    """Return a single snapshot."""

    try:
        snapshot = get_snapshot(db, snapshot_id)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(snapshot)


@router.patch("/{snapshot_id}", response_model=SnapshotResponse)
def update_snapshot_endpoint(
    snapshot_id: str,
    payload: SnapshotUpdate,
    db: Session = Depends(get_db),
) -> SnapshotResponse:
    """Update snapshot metadata."""

    update_kwargs = payload.model_dump(exclude_unset=True)
    try:
        snapshot = update_snapshot(db, snapshot_id, **update_kwargs)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(snapshot)


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot_endpoint(snapshot_id: str, db: Session = Depends(get_db)) -> Response:
    """Delete a snapshot."""

    try:
        delete_snapshot(db, snapshot_id)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
