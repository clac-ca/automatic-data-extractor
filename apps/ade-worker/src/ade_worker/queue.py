"""Queues for environments and runs stored in the ADE database.

Design goals:
- Works on SQLite and SQL Server/Azure SQL.
- Atomic claim per table.
- Runs use leases + heartbeats for long-running work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

# --- SQL snippets ---

SQLITE_BEGIN_IMMEDIATE = "BEGIN IMMEDIATE"

SQLITE_CLAIM_ENVIRONMENT = """    UPDATE environments
SET
    status = 'building',
    claimed_by = :worker_id,
    claim_expires_at = :lease_expires_at,
    error_message = NULL,
    updated_at = :now
WHERE id = (
    SELECT id
    FROM environments
    WHERE status = 'queued'
    ORDER BY created_at ASC
    LIMIT 1
)
AND status = 'queued'
RETURNING id;
"""

MSSQL_CLAIM_ENVIRONMENT = """    ;WITH next_env AS (
    SELECT TOP (1) *
    FROM environments WITH (UPDLOCK, READPAST, ROWLOCK, READCOMMITTEDLOCK)
    WHERE status = 'queued'
    ORDER BY created_at ASC
)
UPDATE next_env
SET
    status = 'building',
    claimed_by = :worker_id,
    claim_expires_at = :lease_expires_at,
    error_message = NULL,
    updated_at = :now
OUTPUT inserted.id;
"""

SQLITE_CLAIM_RUN = """    UPDATE runs
SET
    status = 'running',
    claimed_by = :worker_id,
    claim_expires_at = :lease_expires_at,
    started_at = COALESCE(started_at, :now),
    attempt_count = attempt_count + 1,
    error_message = NULL
WHERE id = (
    SELECT runs.id
    FROM runs
    JOIN environments
      ON environments.workspace_id = runs.workspace_id
     AND environments.configuration_id = runs.configuration_id
     AND environments.engine_spec = runs.engine_spec
     AND environments.deps_digest = runs.deps_digest
    WHERE runs.status = 'queued'
      AND runs.available_at <= :now
      AND runs.attempt_count < runs.max_attempts
      AND environments.status = 'ready'
    ORDER BY runs.available_at ASC, runs.created_at ASC
    LIMIT 1
)
AND status = 'queued'
RETURNING id, attempt_count, max_attempts;
"""

MSSQL_CLAIM_RUN = """    ;WITH next_run AS (
    SELECT TOP (1) runs.*
    FROM runs WITH (UPDLOCK, READPAST, ROWLOCK, READCOMMITTEDLOCK)
    JOIN environments WITH (READPAST)
      ON environments.workspace_id = runs.workspace_id
     AND environments.configuration_id = runs.configuration_id
     AND environments.engine_spec = runs.engine_spec
     AND environments.deps_digest = runs.deps_digest
    WHERE runs.status = 'queued'
      AND runs.available_at <= :now
      AND runs.attempt_count < runs.max_attempts
      AND environments.status = 'ready'
    ORDER BY runs.available_at ASC, runs.created_at ASC
)
UPDATE next_run
SET
    status = 'running',
    claimed_by = :worker_id,
    claim_expires_at = :lease_expires_at,
    started_at = COALESCE(started_at, :now),
    attempt_count = attempt_count + 1,
    error_message = NULL
OUTPUT inserted.id, inserted.attempt_count, inserted.max_attempts;
"""

ENVIRONMENT_ACK_SUCCESS = """    UPDATE environments
SET
    status = 'ready',
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = NULL,
    updated_at = :now
WHERE id = :env_id
  AND status = 'building'
  AND claimed_by = :worker_id;
"""

ENVIRONMENT_ACK_FAILURE = """    UPDATE environments
SET
    status = 'failed',
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = :error_message,
    updated_at = :now
WHERE id = :env_id
  AND status = 'building'
  AND claimed_by = :worker_id;
"""

ENVIRONMENT_HEARTBEAT = """    UPDATE environments
SET
    claim_expires_at = :lease_expires_at
WHERE id = :env_id
  AND status = 'building'
  AND claimed_by = :worker_id;
"""

ENVIRONMENT_SELECT_EXPIRED = """    SELECT id
FROM environments
WHERE status = 'building'
  AND claim_expires_at IS NOT NULL
  AND claim_expires_at < :now
ORDER BY claim_expires_at ASC;
"""

ENVIRONMENT_EXPIRE_REQUEUE = """    UPDATE environments
SET
    status = 'queued',
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = 'lease expired',
    updated_at = :now
WHERE id = :env_id
  AND status = 'building';
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

RUN_RELEASE_ENV = """    UPDATE runs
SET
    status = 'queued',
    available_at = :retry_at,
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = :error_message,
    completed_at = NULL,
    attempt_count = CASE WHEN attempt_count > 0 THEN attempt_count - 1 ELSE 0 END
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

RUN_SELECT_EXPIRED = """    SELECT id, attempt_count, max_attempts
FROM runs
WHERE status = 'running'
  AND claim_expires_at IS NOT NULL
  AND claim_expires_at < :now
ORDER BY claim_expires_at ASC;
"""

RUN_EXPIRE_REQUEUE = """    UPDATE runs
SET
    status = 'queued',
    available_at = :retry_at,
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = 'lease expired',
    completed_at = NULL
WHERE id = :run_id
  AND status = 'running';
"""

RUN_EXPIRE_TERMINAL = """    UPDATE runs
SET
    status = 'failed',
    completed_at = :now,
    claimed_by = NULL,
    claim_expires_at = NULL,
    error_message = 'lease expired'
WHERE id = :run_id
  AND status = 'running';
"""

# --- Types ---

@dataclass(frozen=True, slots=True)
class EnvironmentClaim:
    id: str


@dataclass(frozen=True, slots=True)
class RunClaim:
    id: str
    attempt_count: int
    max_attempts: int


def _row_to_run_claim(row: dict[str, object]) -> RunClaim:
    data = dict(row)
    return RunClaim(
        id=str(data.get("id") or ""),
        attempt_count=int(data.get("attempt_count") or 0),
        max_attempts=int(data.get("max_attempts") or 0),
    )


class EnvironmentQueue:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @property
    def dialect(self) -> str:
        return self._engine.dialect.name

    def claim_next(self, *, worker_id: str, now: datetime, lease_seconds: int) -> EnvironmentClaim | None:
        lease_expires_at = now + timedelta(seconds=int(lease_seconds))
        params = {
            "worker_id": worker_id,
            "now": now,
            "lease_expires_at": lease_expires_at,
        }

        if self.dialect == "sqlite":
            with self._engine.connect() as conn:
                try:
                    conn.exec_driver_sql(SQLITE_BEGIN_IMMEDIATE)
                    row = conn.execute(text(SQLITE_CLAIM_ENVIRONMENT), params).mappings().first()
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            return EnvironmentClaim(id=str(row["id"])) if row else None

        if self.dialect == "mssql":
            with self._engine.begin() as conn:
                row = conn.execute(text(MSSQL_CLAIM_ENVIRONMENT), params).mappings().first()
            return EnvironmentClaim(id=str(row["id"])) if row else None

        raise ValueError(f"Unsupported dialect: {self.dialect}")

    def heartbeat(
        self,
        *,
        conn: Connection | None = None,
        env_id: str,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> bool:
        lease_expires_at = now + timedelta(seconds=int(lease_seconds))
        stmt = text(ENVIRONMENT_HEARTBEAT)
        params = {
            "env_id": env_id,
            "worker_id": worker_id,
            "lease_expires_at": lease_expires_at,
        }
        if conn is not None:
            result = conn.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

        with self._engine.begin() as tx:
            result = tx.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def ack_success(
        self,
        *,
        conn: Connection | None = None,
        env_id: str,
        worker_id: str,
        now: datetime,
    ) -> bool:
        stmt = text(ENVIRONMENT_ACK_SUCCESS)
        params = {"env_id": env_id, "worker_id": worker_id, "now": now}
        if conn is not None:
            result = conn.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)
        with self._engine.begin() as tx:
            result = tx.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def ack_failure(
        self,
        *,
        conn: Connection | None = None,
        env_id: str,
        worker_id: str,
        now: datetime,
        error_message: str,
    ) -> bool:
        stmt = text(ENVIRONMENT_ACK_FAILURE)
        params = {
            "env_id": env_id,
            "worker_id": worker_id,
            "now": now,
            "error_message": error_message,
        }
        if conn is not None:
            result = conn.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)
        with self._engine.begin() as tx:
            result = tx.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def release_for_env(
        self,
        *,
        conn: Connection | None = None,
        run_id: str,
        worker_id: str,
        retry_at: datetime,
        error_message: str,
    ) -> bool:
        stmt = text(RUN_RELEASE_ENV)
        params = {
            "run_id": run_id,
            "worker_id": worker_id,
            "retry_at": retry_at,
            "error_message": error_message,
        }
        if conn is not None:
            result = conn.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)
        with self._engine.begin() as tx:
            result = tx.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def expire_stuck(self, *, now: datetime) -> int:
        processed = 0
        with self._engine.begin() as conn:
            rows = conn.execute(text(ENVIRONMENT_SELECT_EXPIRED), {"now": now}).mappings().all()
            for row in rows:
                processed += 1
                env_id = str(row["id"])
                conn.execute(text(ENVIRONMENT_EXPIRE_REQUEUE), {"env_id": env_id, "now": now})
        return processed


class RunQueue:
    def __init__(self, engine: Engine, *, backoff: Callable[[int], int]) -> None:
        self._engine = engine
        self._backoff = backoff

    @property
    def dialect(self) -> str:
        return self._engine.dialect.name

    def claim_next(self, *, worker_id: str, now: datetime, lease_seconds: int) -> RunClaim | None:
        lease_expires_at = now + timedelta(seconds=int(lease_seconds))

        params = {
            "worker_id": worker_id,
            "now": now,
            "lease_expires_at": lease_expires_at,
        }

        if self.dialect == "sqlite":
            with self._engine.connect() as conn:
                try:
                    conn.exec_driver_sql(SQLITE_BEGIN_IMMEDIATE)
                    row = conn.execute(text(SQLITE_CLAIM_RUN), params).mappings().first()
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            return _row_to_run_claim(row) if row else None

        if self.dialect == "mssql":
            with self._engine.begin() as conn:
                row = conn.execute(text(MSSQL_CLAIM_RUN), params).mappings().first()
            return _row_to_run_claim(row) if row else None

        raise ValueError(f"Unsupported dialect: {self.dialect}")

    def heartbeat(
        self,
        *,
        conn: Connection | None = None,
        run_id: str,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> bool:
        lease_expires_at = now + timedelta(seconds=int(lease_seconds))
        stmt = text(RUN_HEARTBEAT)
        params = {
            "run_id": run_id,
            "worker_id": worker_id,
            "lease_expires_at": lease_expires_at,
        }
        if conn is not None:
            result = conn.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

        with self._engine.begin() as tx:
            result = tx.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def ack_success(
        self,
        *,
        conn: Connection | None = None,
        run_id: str,
        worker_id: str,
        now: datetime,
    ) -> bool:
        stmt = text(RUN_ACK_SUCCESS)
        params = {"run_id": run_id, "worker_id": worker_id, "now": now}
        if conn is not None:
            result = conn.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)
        with self._engine.begin() as tx:
            result = tx.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def ack_failure(
        self,
        *,
        conn: Connection | None = None,
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

        if conn is not None:
            result = conn.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

        with self._engine.begin() as tx:
            result = tx.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def expire_stuck(self, *, now: datetime) -> int:
        """Requeue/terminal-fail expired running runs."""
        processed = 0
        with self._engine.begin() as conn:
            rows = conn.execute(text(RUN_SELECT_EXPIRED), {"now": now}).mappings().all()
            for row in rows:
                processed += 1
                run_id = str(row["id"])
                attempt_count = int(row.get("attempt_count") or 0)
                max_attempts = int(row.get("max_attempts") or 0)

                if attempt_count >= max_attempts:
                    conn.execute(text(RUN_EXPIRE_TERMINAL), {"run_id": run_id, "now": now})
                else:
                    delay = int(self._backoff(attempt_count))
                    conn.execute(
                        text(RUN_EXPIRE_REQUEUE),
                        {"run_id": run_id, "retry_at": now + timedelta(seconds=delay)},
                    )
        return processed


__all__ = ["EnvironmentClaim", "EnvironmentQueue", "RunClaim", "RunQueue"]
