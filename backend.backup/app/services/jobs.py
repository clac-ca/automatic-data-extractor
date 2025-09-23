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

from ..models import Document, Job
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
    payload["input_document_id"] = job.input_document_id
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


def _summarise_document(document: Document) -> dict[str, Any]:
    is_deleted = document.deleted_at is not None
    download_url = None if is_deleted else f"/documents/{document.document_id}/download"
    return {
        "document_id": document.document_id,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "byte_size": document.byte_size,
        "created_at": document.created_at,
        "is_deleted": is_deleted,
        "download_url": download_url,
    }


def _load_input_document(db: Session, job: Job) -> Document:
    document = db.get(Document, job.input_document_id)
    if document is None:
        raise InputDocumentNotFoundError(job.input_document_id)
    return document


def _load_output_documents(db: Session, job: Job) -> list[Document]:
    statement = (
        select(Document)
        .where(Document.produced_by_job_id == job.job_id)
        .order_by(Document.created_at.asc(), Document.document_id.asc())
    )
    return list(db.scalars(statement))


def build_job_projection(
    db: Session,
    job: Job,
) -> dict[str, Any]:
    """Return a serialisable dictionary representing the job and linked documents."""

    input_document = _load_input_document(db, job)
    output_documents = _load_output_documents(db, job)

    payload: dict[str, Any] = {
        "job_id": job.job_id,
        "document_type": job.document_type,
        "configuration_id": job.configuration_id,
        "configuration_version": job.configuration_version,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "created_by": job.created_by,
        "metrics": _coerce_dict(job.metrics),
        "logs": _coerce_logs(job.logs),
        "input_document": _summarise_document(input_document),
        "output_documents": [
            _summarise_document(document) for document in output_documents
        ],
    }

    return payload


def summarise_job(job: Job) -> dict[str, Any]:
    """Return a minimal representation suitable for history views."""

    return {
        "job_id": job.job_id,
        "status": job.status,
        "configuration_id": job.configuration_id,
        "configuration_version": job.configuration_version,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


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


class InputDocumentNotFoundError(Exception):
    """Raised when the referenced input document cannot be found."""

    def __init__(self, document_id: str) -> None:
        super().__init__(f"Document '{document_id}' was not found")
        self.document_id = document_id


def list_jobs(
    db: Session,
    *,
    input_document_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Job]:
    """Return jobs ordered by creation time (newest first)."""

    statement = select(Job).order_by(
        Job.created_at.desc(),
        Job.job_id.desc(),
    )

    if input_document_id is not None:
        statement = statement.where(Job.input_document_id == input_document_id)

    if offset:
        statement = statement.offset(offset)
    if limit is not None:
        statement = statement.limit(limit)

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
    input_document_id: str,
    status: str = "pending",
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

    document_id = str(input_document_id).strip()
    input_document = db.get(Document, document_id)
    if input_document is None:
        raise InputDocumentNotFoundError(document_id)

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
        input_document_id=input_document.document_id,
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
    metrics_changed = False

    if status is not None:
        _ensure_valid_status(status)
        if status != job.status:
            job.status = status
            status_changed = True

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

    if metrics_changed:
        result_details: dict[str, Any] = {
            "metrics": _coerce_dict(job.metrics)
        }

        results_payload = _job_event_payload(job, extra=result_details)
        _record_job_event(
            db,
            job=job,
            event_type="job.metrics.updated",
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
    "InputDocumentNotFoundError",
    "generate_job_id",
    "create_job",
    "get_job",
    "list_jobs",
    "update_job",
    "build_job_projection",
    "summarise_job",
]

