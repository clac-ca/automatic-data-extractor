"""Persistence helpers for automatic maintenance status payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from time import sleep
from typing import Any

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from ..models import MaintenanceStatus
from .documents import ExpiredDocumentPurgeSummary

_AUTO_PURGE_KEY = "automatic_document_purge"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    record["recorded_at"] = _now_iso()

    last_error: Exception | None = None
    for attempt in range(10):
        try:
            with db.begin_nested():
                status = db.get(MaintenanceStatus, _AUTO_PURGE_KEY)
                if status is None:
                    status = MaintenanceStatus(key=_AUTO_PURGE_KEY)
                    db.add(status)
                status.payload = record
            return dict(status.payload)
        except IntegrityError as exc:
            last_error = exc
            db.rollback()
            continue
        except OperationalError as exc:
            last_error = exc
            if "database is locked" in str(exc).lower():
                db.rollback()
                sleep(0.2)
                continue
            raise

    if last_error is not None:  # pragma: no cover - defensive fallback
        raise last_error
    raise RuntimeError("Unable to persist maintenance status")  # pragma: no cover


def record_auto_purge_success(
    db: Session,
    *,
    summary: ExpiredDocumentPurgeSummary,
    started_at: str,
    completed_at: str,
    interval_seconds: int,
) -> dict[str, Any]:
    """Persist the outcome of a successful automatic purge run."""

    payload = {
        "status": "succeeded",
        "dry_run": summary.dry_run,
        "processed_count": summary.processed_count,
        "bytes_reclaimed": summary.bytes_reclaimed,
        "started_at": started_at,
        "completed_at": completed_at,
        "interval_seconds": interval_seconds,
        "error": None,
    }
    return _upsert_payload(db, payload)


def record_auto_purge_failure(
    db: Session,
    *,
    started_at: str,
    completed_at: str | None,
    interval_seconds: int,
    error: str,
) -> dict[str, Any]:
    """Persist the outcome of a failed automatic purge run."""

    payload = {
        "status": "failed",
        "dry_run": None,
        "processed_count": None,
        "bytes_reclaimed": None,
        "started_at": started_at,
        "completed_at": completed_at,
        "interval_seconds": interval_seconds,
        "error": error,
    }
    return _upsert_payload(db, payload)


def get_auto_purge_status(db: Session) -> dict[str, Any] | None:
    """Return the most recently recorded automatic purge status if available."""

    status = db.get(MaintenanceStatus, _AUTO_PURGE_KEY)
    if status is None:
        return None
    return dict(status.payload)


__all__ = [
    "get_auto_purge_status",
    "record_auto_purge_failure",
    "record_auto_purge_success",
]

