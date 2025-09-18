"""Job orchestration helpers.

Functions here coordinate job lifecycle invariants, generate sequential
identifiers, and normalise JSON payloads before persistence. Keeping the
logic in one place avoids divergent behaviour between API consumers and
background processors.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job
from .configuration_revisions import resolve_configuration_revision

VALID_STATUSES = {"pending", "running", "completed", "failed"}
FINISHED_STATUSES = {"completed", "failed"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_job_id(db: Session, *, now: datetime | None = None) -> str:
    """Return a sequential job identifier grouped by UTC date."""

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    date_prefix = current.strftime("%Y_%m_%d")
    prefix = f"job_{date_prefix}_"
    statement = (
        select(Job.job_id)
        .where(Job.job_id.like(f"{prefix}%"))
        .order_by(Job.job_id.desc())
        .limit(1)
    )
    last_id = db.scalars(statement).first()
    last_seq = 0
    if last_id:
        suffix = last_id[len(prefix) :]
        if suffix.isdigit():
            last_seq = int(suffix)

    sequence = last_seq + 1
    candidate = f"{prefix}{sequence:04d}"
    while db.get(Job, candidate) is not None:
        sequence += 1
        candidate = f"{prefix}{sequence:04d}"

    return candidate


def _ensure_valid_status(status: str) -> None:
    if status not in VALID_STATUSES:
        allowed = ", ".join(sorted(VALID_STATUSES))
        raise InvalidJobStatusError(
            status, f"Invalid job status '{status}'. Allowed values are {allowed}"
        )


def _to_plain(data: Any) -> Any:
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data


def _coerce_dict(data: Any | None) -> dict[str, Any]:
    if data is None:
        return {}
    return dict(_to_plain(data))


def _coerce_outputs(outputs: dict[str, Any] | None) -> dict[str, Any]:
    if outputs is None:
        return {}
    return {name: dict(_to_plain(value)) for name, value in outputs.items()}


def _coerce_logs(entries: list[Any] | None) -> list[dict[str, Any]]:
    if entries is None:
        return []
    return [dict(_to_plain(entry)) for entry in entries]


class JobNotFoundError(Exception):
    """Raised when a job identifier cannot be located."""

    def __init__(self, job_id: str) -> None:
        message = f"Job '{job_id}' was not found"
        super().__init__(message)
        self.job_id = job_id


class JobImmutableError(Exception):
    """Raised when attempting to mutate a finished job."""

    def __init__(self, job_id: str) -> None:
        message = f"Job '{job_id}' can no longer be modified"
        super().__init__(message)
        self.job_id = job_id


class InvalidJobStatusError(Exception):
    """Raised when an invalid job status is supplied."""

    def __init__(self, status: str, message: str | None = None) -> None:
        super().__init__(message or f"Invalid job status '{status}'")
        self.status = status


def list_jobs(db: Session) -> list[Job]:
    """Return jobs ordered by creation time (newest first)."""

    statement = select(Job).order_by(Job.created_at.desc())
    return list(db.scalars(statement))


def get_job(db: Session, job_id: str) -> Job:
    """Fetch a job by identifier or raise :class:`JobNotFoundError`."""

    job = db.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(job_id)
    return job


def create_job(
    db: Session,
    *,
    document_type: str,
    created_by: str,
    input_payload: dict[str, Any],
    status: str = "pending",
    outputs: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    logs: list[dict[str, Any]] | None = None,
    configuration_revision_id: str | None = None,
) -> Job:
    """Persist and return a new job tied to a configuration revision."""

    _ensure_valid_status(status)
    revision = resolve_configuration_revision(
        db,
        document_type=document_type,
        configuration_revision_id=configuration_revision_id,
    )

    job_id = generate_job_id(db)
    job = Job(
        job_id=job_id,
        document_type=document_type,
        configuration_revision_id=revision.configuration_revision_id,
        configuration_revision_number=revision.revision_number,
        status=status,
        created_by=created_by,
        input=_coerce_dict(input_payload),
        outputs=_coerce_outputs(outputs),
        metrics=_coerce_dict(metrics),
        logs=_coerce_logs(logs),
    )

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(
    db: Session,
    job_id: str,
    *,
    status: str | None = None,
    outputs: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    logs: list[dict[str, Any]] | None = None,
) -> Job:
    """Apply updates to a job that is still running."""

    job = get_job(db, job_id)
    if job.status in FINISHED_STATUSES:
        raise JobImmutableError(job_id)

    if status is not None:
        _ensure_valid_status(status)
        job.status = status
    if outputs is not None:
        job.outputs = _coerce_outputs(outputs)
    if metrics is not None:
        job.metrics = _coerce_dict(metrics)
    if logs is not None:
        job.logs = _coerce_logs(logs)

    job.updated_at = _utcnow_iso()
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


__all__ = [
    "InvalidJobStatusError",
    "JobImmutableError",
    "JobNotFoundError",
    "generate_job_id",
    "create_job",
    "get_job",
    "list_jobs",
    "update_job",
]

