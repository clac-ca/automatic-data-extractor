"""Run queue + environment lease helpers stored in the ADE database.

Design goals:
- Postgres-only (FOR UPDATE SKIP LOCKED for runs).
- Atomic claims.
- Runs use leases + heartbeats for long-running work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# --- SQL snippets ---

ENVIRONMENT_CLAIM_BY_ID = """    UPDATE environments
SET
    status = 'building',
    claimed_by = :worker_id,
    claim_expires_at = :lease_expires_at,
    error_message = NULL,
    updated_at = :now
WHERE id = :env_id
  AND (
    status IN ('queued', 'failed')
    OR (
      status = 'building'
      AND (claim_expires_at IS NULL OR claim_expires_at < :now)
    )
  )
RETURNING id;
"""

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
    def __init__(self, engine: Engine, SessionLocal: sessionmaker[Session]) -> None:
        self._engine = engine
        self._SessionLocal = SessionLocal

    @property
    def dialect(self) -> str:
        return self._engine.dialect.name

    def claim_for_build(
        self,
        *,
        env_id: str,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> EnvironmentClaim | None:
        lease_expires_at = now + timedelta(seconds=int(lease_seconds))
        params = {
            "env_id": env_id,
            "worker_id": worker_id,
            "now": now,
            "lease_expires_at": lease_expires_at,
        }

        if self.dialect != "postgresql":
            raise ValueError(f"Unsupported dialect: {self.dialect}")

        with self._SessionLocal.begin() as session:
            row = session.execute(text(ENVIRONMENT_CLAIM_BY_ID), params).mappings().first()
        return EnvironmentClaim(id=str(row["id"])) if row else None

    def heartbeat(
        self,
        *,
        session: Session | None = None,
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
        if session is not None:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

        with self._SessionLocal.begin() as session:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def ack_success(
        self,
        *,
        session: Session | None = None,
        env_id: str,
        worker_id: str,
        now: datetime,
    ) -> bool:
        stmt = text(ENVIRONMENT_ACK_SUCCESS)
        params = {"env_id": env_id, "worker_id": worker_id, "now": now}
        if session is not None:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)
        with self._SessionLocal.begin() as session:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def ack_failure(
        self,
        *,
        session: Session | None = None,
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
        if session is not None:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)
        with self._SessionLocal.begin() as session:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

class RunQueue:
    def __init__(
        self,
        engine: Engine,
        SessionLocal: sessionmaker[Session],
        *,
        backoff_base_seconds: int,
        backoff_max_seconds: int,
    ) -> None:
        self._engine = engine
        self._SessionLocal = SessionLocal
        self._backoff_base_seconds = int(backoff_base_seconds)
        self._backoff_max_seconds = int(backoff_max_seconds)

    @property
    def dialect(self) -> str:
        return self._engine.dialect.name

    def claim_next(self, *, worker_id: str, now: datetime, lease_seconds: int) -> RunClaim | None:
        claims = self.claim_batch(
            worker_id=worker_id,
            now=now,
            lease_seconds=lease_seconds,
            limit=1,
        )
        return claims[0] if claims else None

    def claim_batch(
        self,
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

        if self.dialect != "postgresql":
            raise ValueError(f"Unsupported dialect: {self.dialect}")

        with self._SessionLocal.begin() as session:
            rows = session.execute(text(POSTGRES_CLAIM_RUN_BATCH), params).mappings().all()
        return [_row_to_run_claim(row) for row in rows]

    def heartbeat(
        self,
        *,
        session: Session | None = None,
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
        if session is not None:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

        with self._SessionLocal.begin() as session:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def ack_success(
        self,
        *,
        session: Session | None = None,
        run_id: str,
        worker_id: str,
        now: datetime,
    ) -> bool:
        stmt = text(RUN_ACK_SUCCESS)
        params = {"run_id": run_id, "worker_id": worker_id, "now": now}
        if session is not None:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)
        with self._SessionLocal.begin() as session:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def ack_failure(
        self,
        *,
        session: Session | None = None,
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

        if session is not None:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

        with self._SessionLocal.begin() as session:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def release_for_env(
        self,
        *,
        session: Session | None = None,
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
        if session is not None:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)
        with self._SessionLocal.begin() as session:
            result = session.execute(stmt, params)
            return bool(getattr(result, "rowcount", 0) == 1)

    def expire_stuck(self, *, now: datetime) -> int:
        """Requeue/terminal-fail expired running runs."""
        with self._SessionLocal.begin() as session:
            terminal_rows = session.execute(
                text(RUN_EXPIRE_TERMINAL_BULK),
                {"now": now},
            ).fetchall()
            requeue_rows = session.execute(
                text(RUN_EXPIRE_REQUEUE_BULK),
                {
                    "now": now,
                    "backoff_base": max(0, self._backoff_base_seconds),
                    "backoff_max": max(0, self._backoff_max_seconds),
                },
            ).fetchall()
        return len(terminal_rows) + len(requeue_rows)


__all__ = ["EnvironmentClaim", "EnvironmentQueue", "RunClaim", "RunQueue"]
