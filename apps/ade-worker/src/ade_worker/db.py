"""Database helpers + SQL for ade-worker (Postgres only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import create_engine, delete, insert, inspect, select, text, update, event
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .schema import documents, environments, run_fields, run_metrics, run_table_columns, runs
from .settings import Settings, get_settings

# Optional dependency (Managed Identity)
try:
    from azure.identity import DefaultAzureCredential  # type: ignore
except ModuleNotFoundError:
    DefaultAzureCredential = None  # type: ignore[assignment]

DEFAULT_AZURE_PG_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

# --- SQL snippets ---

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
  AND attempt_count < max_attempts
RETURNING id;
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
  AND attempt_count >= max_attempts
RETURNING id;
"""

# --- Types ---

@dataclass(frozen=True, slots=True)
class RunClaim:
    id: str
    attempt_count: int
    max_attempts: int


# --- Engine / Session helpers ---

def _apply_sslrootcert(url: URL, sslrootcert: str | None) -> URL:
    if not sslrootcert:
        return url
    query = dict(url.query or {})
    query["sslrootcert"] = sslrootcert
    return url.set(query=query)


def _create_postgres_engine(url: URL, settings: Settings) -> Engine:
    if url.drivername in {"postgresql", "postgres"}:
        url = url.set(drivername="postgresql+psycopg")
    if not url.drivername.startswith("postgresql+psycopg"):
        raise ValueError("For Postgres, use postgresql+psycopg://... (psycopg is required).")

    url = _apply_sslrootcert(url, settings.database_sslrootcert)

    engine = create_engine(
        url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
    )

    if settings.database_auth_mode == "managed_identity":
        attach_azure_postgres_managed_identity(engine)

    return engine


def build_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    if not settings.database_url:
        raise ValueError("Settings.database_url is required.")
    url = make_url(settings.database_url)
    backend = url.get_backend_name()

    if backend == "postgresql":
        return _create_postgres_engine(url, settings)
    raise ValueError("Unsupported database backend. Use postgresql+psycopg://.")


def build_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def assert_tables_exist(
    engine: Engine,
    required_tables: Iterable[str],
    *,
    schema: str | None = None,
) -> None:
    inspector = inspect(engine)
    missing = [t for t in required_tables if not inspector.has_table(t, schema=schema)]
    if missing:
        raise RuntimeError(
            f"Missing required tables: {', '.join(missing)}. "
            "Run migrations via ade-api before starting ade-worker."
        )


# --- Azure Managed Identity auth ---

def attach_azure_postgres_managed_identity(engine: Engine) -> None:
    if DefaultAzureCredential is None:
        raise RuntimeError(
            "Managed Identity requires 'azure-identity'. Install it or set "
            "ADE_DATABASE_AUTH_MODE=password."
        )

    credential = DefaultAzureCredential()
    token_scope = DEFAULT_AZURE_PG_SCOPE

    @event.listens_for(engine, "do_connect", insert=True)
    def _inject_token(_dialect, _conn_rec, _cargs, cparams):
        cparams["password"] = credential.get_token(token_scope).token
        if "sslmode" not in cparams:
            cparams["sslmode"] = "require"


def get_azure_postgres_access_token() -> str:
    if DefaultAzureCredential is None:
        raise RuntimeError(
            "Managed Identity requires 'azure-identity'. Install it or set "
            "ADE_DATABASE_AUTH_MODE=password."
        )
    credential = DefaultAzureCredential()
    token_scope = DEFAULT_AZURE_PG_SCOPE
    return credential.get_token(token_scope).token


# --- Queue / lease helpers ---

def claim_runs(
    SessionLocal: sessionmaker[Session],
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
    with SessionLocal.begin() as session:
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
    SessionLocal: sessionmaker[Session],
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
    with SessionLocal.begin() as session:
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


def ack_environment_success(
    session: Session,
    *,
    env_id: str,
    now: datetime,
) -> bool:
    params = {"env_id": env_id, "now": now}
    result = session.execute(
        text(
            """UPDATE environments
SET
    status = 'ready',
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = NULL,
    updated_at = :now
WHERE id = :env_id;"""
        ),
        params,
    )
    return bool(getattr(result, "rowcount", 0) == 1)


def ack_environment_failure(
    session: Session,
    *,
    env_id: str,
    now: datetime,
    error_message: str,
) -> bool:
    params = {"env_id": env_id, "now": now, "error_message": error_message}
    result = session.execute(
        text(
            """UPDATE environments
SET
    status = 'failed',
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = :error_message,
    updated_at = :now
WHERE id = :env_id;"""
        ),
        params,
    )
    return bool(getattr(result, "rowcount", 0) == 1)


def mark_environment_building(
    session: Session,
    *,
    env_id: str,
    now: datetime,
) -> bool:
    result = session.execute(
        update(environments)
        .where(environments.c.id == env_id)
        .values(
            status="building",
            error_message=None,
            claimed_by=None,
            claim_expires_at=None,
            updated_at=now,
        )
    )
    return bool(getattr(result, "rowcount", 0) == 1)


def advisory_lock(conn, *, key: str) -> None:
    conn.execute(text("SELECT pg_advisory_lock(hashtext(:key))"), {"key": key})


def advisory_unlock(conn, *, key: str) -> None:
    conn.execute(text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": key})


def expire_run_leases(
    SessionLocal: sessionmaker[Session],
    *,
    now: datetime,
    backoff_base_seconds: int,
    backoff_max_seconds: int,
) -> int:
    with SessionLocal.begin() as session:
        terminal_rows = session.execute(
            text(RUN_EXPIRE_TERMINAL_BULK),
            {"now": now},
        ).fetchall()
        requeue_rows = session.execute(
            text(RUN_EXPIRE_REQUEUE_BULK),
            {
                "now": now,
                "backoff_base": max(0, int(backoff_base_seconds)),
                "backoff_max": max(0, int(backoff_max_seconds)),
            },
        ).fetchall()
    return len(terminal_rows) + len(requeue_rows)


# --- Repository helpers ---

def load_environment(SessionLocal: sessionmaker[Session], env_id: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = session.execute(
            select(environments).where(environments.c.id == env_id)
        ).mappings().first()
    return dict(row) if row else None


def load_run(SessionLocal: sessionmaker[Session], run_id: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = session.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
    return dict(row) if row else None


def load_document(SessionLocal: sessionmaker[Session], document_id: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = session.execute(
            select(documents).where(documents.c.id == document_id)
        ).mappings().first()
    return dict(row) if row else None


def ensure_environment(
    SessionLocal: sessionmaker[Session],
    *,
    run: dict[str, Any],
    now: datetime,
) -> dict[str, Any] | None:
    with SessionLocal.begin() as session:
        row = session.execute(
            select(environments).where(
                environments.c.workspace_id == run["workspace_id"],
                environments.c.configuration_id == run["configuration_id"],
                environments.c.engine_spec == run["engine_spec"],
                environments.c.deps_digest == run["deps_digest"],
            )
        ).mappings().first()
        if row:
            return dict(row)

        env_row = {
            "id": str(uuid4()),
            "workspace_id": run["workspace_id"],
            "configuration_id": run["configuration_id"],
            "engine_spec": run["engine_spec"],
            "deps_digest": run["deps_digest"],
            "status": "queued",
            "error_message": None,
            "claimed_by": None,
            "claim_expires_at": None,
            "created_at": now,
            "updated_at": now,
            "last_used_at": None,
            "python_version": None,
            "python_interpreter": None,
            "engine_version": None,
        }
        try:
            with session.begin_nested():
                session.execute(insert(environments).values(**env_row))
        except IntegrityError:
            pass

        row = session.execute(
            select(environments).where(
                environments.c.workspace_id == run["workspace_id"],
                environments.c.configuration_id == run["configuration_id"],
                environments.c.engine_spec == run["engine_spec"],
                environments.c.deps_digest == run["deps_digest"],
            )
        ).mappings().first()
        return dict(row) if row else None


def mark_environment_queued(
    SessionLocal: sessionmaker[Session],
    *,
    env_id: str,
    now: datetime,
    error_message: str,
) -> None:
    with SessionLocal.begin() as session:
        session.execute(
            update(environments)
            .where(environments.c.id == env_id)
            .values(
                status="queued",
                error_message=error_message,
                claimed_by=None,
                claim_expires_at=None,
                updated_at=now,
            )
        )


def record_environment_metadata(
    session: Session,
    *,
    env_id: str,
    now: datetime,
    python_interpreter: str | None,
    python_version: str | None,
    engine_version: str | None,
) -> None:
    session.execute(
        update(environments)
        .where(environments.c.id == env_id)
        .values(
            python_interpreter=python_interpreter,
            python_version=python_version,
            engine_version=engine_version,
            updated_at=now,
        )
    )


def touch_environment_last_used(
    session: Session,
    *,
    env_id: str,
    now: datetime,
) -> None:
    session.execute(
        update(environments)
        .where(environments.c.id == env_id)
        .values(last_used_at=now, updated_at=now)
    )


def record_run_result(
    session: Session,
    *,
    run_id: str,
    completed_at: datetime | None,
    exit_code: int | None,
    output_path: str | None,
    error_message: str | None,
) -> None:
    session.execute(
        update(runs)
        .where(runs.c.id == run_id)
        .values(
            completed_at=completed_at,
            exit_code=exit_code,
            output_path=output_path,
            error_message=error_message,
        )
    )


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


__all__ = [
    "RunClaim",
    "DEFAULT_AZURE_PG_SCOPE",
    "attach_azure_postgres_managed_identity",
    "get_azure_postgres_access_token",
    "build_engine",
    "build_sessionmaker",
    "assert_tables_exist",
    "claim_runs",
    "heartbeat_run",
    "ack_run_success",
    "ack_run_failure",
    "ack_environment_success",
    "ack_environment_failure",
    "mark_environment_building",
    "advisory_lock",
    "advisory_unlock",
    "expire_run_leases",
    "load_environment",
    "load_run",
    "load_document",
    "ensure_environment",
    "mark_environment_queued",
    "record_environment_metadata",
    "touch_environment_last_used",
    "record_run_result",
    "replace_run_metrics",
    "replace_run_fields",
    "replace_run_table_columns",
]
