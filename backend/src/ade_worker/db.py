"""Database helpers for ADE worker (Postgres only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ade_db.schema import (
    configurations,
    files,
    file_versions,
    run_fields,
    run_metrics,
    run_table_columns,
    runs,
)

# --- SQL snippets -----------------------------------------------------------

POSTGRES_CLAIM_RUN_BATCH = """    WITH next_run AS (
    SELECT id
    FROM runs
    WHERE status = 'queued'
      AND available_at <= :now
      AND attempt_count < max_attempts
    ORDER BY available_at ASC, created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT :limit
)
UPDATE runs AS r
SET
    status = 'running',
    claimed_by = :worker_id,
    claim_expires_at = :lease_expires_at,
    started_at = COALESCE(r.started_at, :now),
    attempt_count = r.attempt_count + 1,
    error_message = NULL
FROM next_run
WHERE r.id = next_run.id
RETURNING r.id, r.attempt_count, r.max_attempts;
"""

RUN_ACK_SUCCESS = """    UPDATE runs
SET
    status = 'succeeded',
    completed_at = :now,
    claimed_by = NULL,
    claim_expires_at = NULL
WHERE id = :run_id
  AND status = 'running'
  AND claimed_by = :worker_id;
"""

RUN_ACK_FAILURE_REQUEUE = """    UPDATE runs
SET
    status = 'queued',
    available_at = :retry_at,
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = :error_message,
    completed_at = NULL
WHERE id = :run_id
  AND status = 'running'
  AND claimed_by = :worker_id;
"""

RUN_ACK_FAILURE_TERMINAL = """    UPDATE runs
SET
    status = 'failed',
    completed_at = :now,
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = :error_message
WHERE id = :run_id
  AND status = 'running'
  AND claimed_by = :worker_id;
"""

RUN_HEARTBEAT = """    UPDATE runs
SET
    claim_expires_at = :lease_expires_at
WHERE id = :run_id
  AND status = 'running'
  AND claimed_by = :worker_id;
"""

RUN_EXPIRE_REQUEUE_BULK = """    UPDATE runs
SET
    status = 'queued',
    available_at = :now + make_interval(secs => LEAST(:backoff_max, :backoff_base * POWER(2, GREATEST(attempt_count - 1, 0)))),
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = 'lease expired',
    completed_at = NULL
WHERE status = 'running'
  AND claim_expires_at IS NOT NULL
  AND claim_expires_at < :now
  AND attempt_count < max_attempts;
"""

RUN_EXPIRE_TERMINAL_BULK = """    UPDATE runs
SET
    status = 'failed',
    completed_at = :now,
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = 'lease expired'
WHERE status = 'running'
  AND claim_expires_at IS NOT NULL
  AND claim_expires_at < :now
  AND attempt_count >= max_attempts;
"""


# --- Types ------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RunClaim:
    id: str
    attempt_count: int
    max_attempts: int


# --- Queue / lease helpers --------------------------------------------------

def claim_runs(
    session: Session,
    *,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
    limit: int,
) -> list[RunClaim]:
    lease_expires_at = now + timedelta(seconds=int(lease_seconds))
    params = {
        "worker_id": worker_id,
        "now": now,
        "lease_expires_at": lease_expires_at,
        "limit": max(1, int(limit)),
    }
    rows = session.execute(text(POSTGRES_CLAIM_RUN_BATCH), params).mappings().all()
    return [
        RunClaim(
            id=str(row.get("id") or ""),
            attempt_count=int(row.get("attempt_count") or 0),
            max_attempts=int(row.get("max_attempts") or 0),
        )
        for row in rows
    ]


def heartbeat_run(
    session: Session,
    *,
    run_id: str,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
) -> bool:
    lease_expires_at = now + timedelta(seconds=int(lease_seconds))
    params = {
        "run_id": run_id,
        "worker_id": worker_id,
        "lease_expires_at": lease_expires_at,
    }
    result = session.execute(text(RUN_HEARTBEAT), params)
    return bool(getattr(result, "rowcount", 0) == 1)


def ack_run_success(
    session: Session,
    *,
    run_id: str,
    worker_id: str,
    now: datetime,
) -> bool:
    params = {"run_id": run_id, "worker_id": worker_id, "now": now}
    result = session.execute(text(RUN_ACK_SUCCESS), params)
    return bool(getattr(result, "rowcount", 0) == 1)


def ack_run_failure(
    session: Session,
    *,
    run_id: str,
    worker_id: str,
    now: datetime,
    error_message: str,
    retry_at: datetime | None,
) -> bool:
    if retry_at is None:
        stmt = text(RUN_ACK_FAILURE_TERMINAL)
        params = {
            "run_id": run_id,
            "worker_id": worker_id,
            "now": now,
            "error_message": error_message,
        }
    else:
        stmt = text(RUN_ACK_FAILURE_REQUEUE)
        params = {
            "run_id": run_id,
            "worker_id": worker_id,
            "error_message": error_message,
            "retry_at": retry_at,
        }

    result = session.execute(stmt, params)
    return bool(getattr(result, "rowcount", 0) == 1)


def expire_run_leases(
    session: Session,
    *,
    now: datetime,
    backoff_base_seconds: int,
    backoff_max_seconds: int,
) -> int:
    terminal_count = session.execute(
        text(RUN_EXPIRE_TERMINAL_BULK),
        {"now": now},
    ).rowcount or 0
    requeue_count = session.execute(
        text(RUN_EXPIRE_REQUEUE_BULK),
        {
            "now": now,
            "backoff_base": max(0, int(backoff_base_seconds)),
            "backoff_max": max(0, int(backoff_max_seconds)),
        },
    ).rowcount or 0
    return int(terminal_count) + int(requeue_count)


def next_run_due_at(
    session: Session,
    *,
    now: datetime,
) -> datetime | None:
    row = session.execute(
        select(func.min(runs.c.available_at)).where(
            runs.c.status == "queued",
            runs.c.attempt_count < runs.c.max_attempts,
            runs.c.available_at > now,
        )
    ).scalar()
    return row


# --- Repository helpers -----------------------------------------------------

def load_run(session: Session, run_id: str) -> dict[str, Any] | None:
    row = session.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
    return dict(row) if row else None


def load_file(session: Session, file_id: str) -> dict[str, Any] | None:
    row = session.execute(select(files).where(files.c.id == file_id)).mappings().first()
    return dict(row) if row else None


def load_file_version(
    session: Session,
    file_version_id: str,
) -> dict[str, Any] | None:
    row = session.execute(
        select(file_versions).where(file_versions.c.id == file_version_id)
    ).mappings().first()
    return dict(row) if row else None


def ensure_output_file(
    session: Session,
    *,
    workspace_id: str,
    source_file_id: str,
    name: str,
    name_key: str,
    now: datetime,
) -> dict[str, Any]:
    stmt = select(files).where(
        files.c.workspace_id == workspace_id,
        files.c.kind == "output",
        files.c.name_key == name_key,
        files.c.deleted_at.is_(None),
    )
    row = session.execute(stmt).mappings().first()
    if row:
        return dict(row)

    file_id = uuid4()
    blob_name = f"{workspace_id}/files/{file_id}"
    payload = {
        "id": file_id,
        "workspace_id": workspace_id,
        "kind": "output",
        "name": name,
        "name_key": name_key,
        "blob_name": blob_name,
        "current_version_id": None,
        "source_file_id": source_file_id,
        "comment_count": 0,
        "attributes": {},
        "uploaded_by_user_id": None,
        "assignee_user_id": None,
        "last_run_id": None,
        "deleted_at": None,
        "deleted_by_user_id": None,
        "created_at": now,
        "updated_at": now,
    }
    session.execute(
        pg_insert(files)
        .values(**payload)
        .on_conflict_do_nothing(
            index_elements=["workspace_id", "kind", "name_key"],
            index_where=files.c.deleted_at.is_(None),
        )
    )
    row = session.execute(stmt).mappings().first()
    return dict(row) if row else payload


def create_output_file_version(
    session: Session,
    *,
    file_id: str,
    run_id: str,
    filename_at_upload: str,
    content_type: str | None,
    sha256: str,
    byte_size: int,
    storage_version_id: str | None,
    now: datetime,
) -> dict[str, Any]:
    current = session.execute(
        select(func.max(file_versions.c.version_no)).where(file_versions.c.file_id == file_id)
    ).scalar_one()
    version_no = int(current or 0) + 1
    version_id = uuid4()
    payload = {
        "id": version_id,
        "file_id": file_id,
        "version_no": version_no,
        "origin": "generated",
        "run_id": run_id,
        "created_by_user_id": None,
        "sha256": sha256,
        "byte_size": byte_size,
        "content_type": content_type,
        "filename_at_upload": filename_at_upload,
        "storage_version_id": storage_version_id,
        "created_at": now,
        "updated_at": now,
    }
    session.execute(insert(file_versions).values(**payload))
    session.execute(
        update(files)
        .where(files.c.id == file_id)
        .values(current_version_id=version_id, updated_at=now)
    )
    return payload


def record_run_result(
    session: Session,
    *,
    run_id: str,
    completed_at: datetime | None,
    exit_code: int | None,
    output_file_version_id: str | None,
    error_message: str | None,
) -> None:
    session.execute(
        update(runs)
        .where(runs.c.id == run_id)
        .values(
            completed_at=completed_at,
            exit_code=exit_code,
            output_file_version_id=output_file_version_id,
            error_message=error_message,
        )
    )


def activate_configuration_publish(
    session: Session,
    *,
    workspace_id: str,
    configuration_id: str,
    published_digest: str,
    now: datetime,
) -> bool:
    session.execute(
        update(configurations)
        .where(
            configurations.c.workspace_id == workspace_id,
            configurations.c.status == "active",
            configurations.c.id != configuration_id,
        )
        .values(status="archived", updated_at=now)
    )
    result = session.execute(
        update(configurations)
        .where(
            configurations.c.id == configuration_id,
            configurations.c.workspace_id == workspace_id,
            configurations.c.status == "draft",
        )
        .values(
            status="active",
            published_digest=published_digest,
            activated_at=now,
            updated_at=now,
        )
    )
    return bool((result.rowcount or 0) == 1)


def replace_run_metrics(
    session: Session,
    *,
    run_id: str,
    metrics: dict[str, Any] | None,
) -> None:
    session.execute(delete(run_metrics).where(run_metrics.c.run_id == run_id))
    if not metrics:
        return
    payload = dict(metrics)
    payload["run_id"] = run_id
    session.execute(insert(run_metrics).values(**payload))


def replace_run_fields(
    session: Session,
    *,
    run_id: str,
    rows: list[dict[str, Any]],
) -> None:
    session.execute(delete(run_fields).where(run_fields.c.run_id == run_id))
    if not rows:
        return
    payload = [dict(row, run_id=run_id) for row in rows]
    session.execute(insert(run_fields), payload)


def replace_run_table_columns(
    session: Session,
    *,
    run_id: str,
    rows: list[dict[str, Any]],
) -> None:
    session.execute(delete(run_table_columns).where(run_table_columns.c.run_id == run_id))
    if not rows:
        return
    payload = [dict(row, run_id=run_id) for row in rows]
    session.execute(insert(run_table_columns), payload)


# --- Exports ----------------------------------------------------------------


__all__ = [
    "RunClaim",
    "claim_runs",
    "heartbeat_run",
    "ack_run_success",
    "ack_run_failure",
    "expire_run_leases",
    "next_run_due_at",
    "load_run",
    "load_file",
    "load_file_version",
    "ensure_output_file",
    "create_output_file_version",
    "record_run_result",
    "activate_configuration_publish",
    "replace_run_metrics",
    "replace_run_fields",
    "replace_run_table_columns",
]
