"""Job orchestration helpers.

Functions here coordinate job lifecycle invariants, generate sequential
identifiers, and normalise JSON payloads before persistence. Keeping the
logic in one place avoids divergent behaviour between API consumers and
background processors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job
from .events import EventRecord, record_event
from .configurations import resolve_configuration


logger = logging.getLogger(__name__)

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


def _job_event_payload(job: Job, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "document_type": job.document_type,
        "configuration_id": job.configuration_id,
        "configuration_version": job.configuration_version,
        "status": job.status,
    }
    if extra:
        payload.update(extra)
    return payload


def _record_job_event(
    db: Session,
    *,
    job: Job,
    event_type: str,
    actor_type: str | None,
    actor_id: str | None,
    actor_label: str | None,
    source: str | None,
    request_id: str | None,
    occurred_at: str | None,
    payload: dict[str, Any],
) -> None:
    record = EventRecord(
        event_type=event_type,
        entity_type="job",
        entity_id=job.job_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_label=actor_label,
        source=source,
        request_id=request_id,
        occurred_at=occurred_at,
        payload=payload,
    )

    try:
        record_event(db, record)
    except Exception:
        logger.exception(
            "Failed to record job event",
            extra={
                "job_id": job.job_id,
                "event_type": event_type,
                "source": source,
            },
        )


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
    configuration_id: str | None = None,
    event_actor_type: str | None = None,
    event_actor_id: str | None = None,
    event_actor_label: str | None = None,
    event_source: str | None = None,
    event_request_id: str | None = None,
) -> Job:
    """Persist and return a new job tied to a configuration version."""

    _ensure_valid_status(status)
    configuration = resolve_configuration(
        db,
        document_type=document_type,
        configuration_id=configuration_id,
    )

    job_id = generate_job_id(db)
    job = Job(
        job_id=job_id,
        document_type=document_type,
        configuration_id=configuration.configuration_id,
        configuration_version=configuration.version,
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

    actor_label = event_actor_label or job.created_by
    payload = _job_event_payload(
        job,
        extra={
            "created_by": job.created_by,
            "input": _coerce_dict(job.input),
            "outputs": _coerce_outputs(job.outputs),
            "metrics": _coerce_dict(job.metrics),
        },
    )
    _record_job_event(
        db,
        job=job,
        event_type="job.created",
        actor_type=event_actor_type,
        actor_id=event_actor_id,
        actor_label=actor_label,
        source=event_source,
        request_id=event_request_id,
        occurred_at=job.created_at,
        payload=payload,
    )
    return job


def update_job(
    db: Session,
    job_id: str,
    *,
    status: str | None = None,
    outputs: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    logs: list[dict[str, Any]] | None = None,
    event_actor_type: str | None = None,
    event_actor_id: str | None = None,
    event_actor_label: str | None = None,
    event_source: str | None = None,
    event_request_id: str | None = None,
) -> Job:
    """Apply updates to a job that is still running."""

    job = get_job(db, job_id)
    if job.status in FINISHED_STATUSES:
        raise JobImmutableError(job_id)

    original_status = job.status
    status_changed = False
    outputs_changed = False
    metrics_changed = False

    if status is not None:
        _ensure_valid_status(status)
        if status != job.status:
            job.status = status
            status_changed = True

    if outputs is not None:
        new_outputs = _coerce_outputs(outputs)
        if new_outputs != job.outputs:
            job.outputs = new_outputs
            outputs_changed = True

    if metrics is not None:
        new_metrics = _coerce_dict(metrics)
        if new_metrics != job.metrics:
            job.metrics = new_metrics
            metrics_changed = True

    if logs is not None:
        job.logs = _coerce_logs(logs)

    job.updated_at = _utcnow_iso()
    db.add(job)
    db.commit()
    db.refresh(job)

    actor_label = event_actor_label or job.created_by

    if status_changed:
        status_payload = _job_event_payload(
            job,
            extra={
                "from_status": original_status,
                "to_status": job.status,
            },
        )
        _record_job_event(
            db,
            job=job,
            event_type=f"job.status.{job.status}",
            actor_type=event_actor_type,
            actor_id=event_actor_id,
            actor_label=actor_label,
            source=event_source,
            request_id=event_request_id,
            occurred_at=job.updated_at,
            payload=status_payload,
        )

    if outputs_changed or metrics_changed:
        result_details: dict[str, Any] = {
            "outputs": _coerce_outputs(job.outputs),
            "metrics": _coerce_dict(job.metrics),
        }

        results_payload = _job_event_payload(job, extra=result_details)
        _record_job_event(
            db,
            job=job,
            event_type="job.results.published",
            actor_type=event_actor_type,
            actor_id=event_actor_id,
            actor_label=actor_label,
            source=event_source,
            request_id=event_request_id,
            occurred_at=job.updated_at,
            payload=results_payload,
        )

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

