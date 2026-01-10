from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine, insert, select, update

from ade_worker.queue import EnvironmentQueue, RunQueue
from ade_worker.schema import environments, metadata, runs


def _engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def _insert_environment(
    engine,
    *,
    env_id: str,
    workspace_id: str,
    configuration_id: str,
    engine_spec: str,
    deps_digest: str,
    status: str,
    now: datetime,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(environments).values(
                id=env_id,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                engine_spec=engine_spec,
                deps_digest=deps_digest,
                status=status,
                error_message=None,
                claimed_by=None,
                claim_expires_at=None,
                created_at=now - timedelta(minutes=5),
                updated_at=now - timedelta(minutes=5),
                last_used_at=None,
                python_version=None,
                python_interpreter=None,
                engine_version=None,
            )
        )


def _insert_run(
    engine,
    *,
    run_id: str,
    workspace_id: str,
    configuration_id: str,
    engine_spec: str,
    deps_digest: str,
    status: str,
    now: datetime,
    attempt_count: int = 0,
    max_attempts: int = 3,
    claim_expires_at: datetime | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(runs).values(
                id=run_id,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                input_document_id="doc-1",
                input_sheet_names=None,
                run_options=None,
                output_path=None,
                engine_spec=engine_spec,
                deps_digest=deps_digest,
                status=status,
                available_at=now - timedelta(minutes=1),
                attempt_count=attempt_count,
                max_attempts=max_attempts,
                claimed_by=None,
                claim_expires_at=claim_expires_at,
                exit_code=None,
                error_message=None,
                created_at=now - timedelta(minutes=10),
                started_at=None,
                completed_at=None,
            )
        )


def test_run_claim_requires_ready_environment() -> None:
    engine = _engine()
    now = datetime(2025, 1, 10, 12, 0, 0)

    _insert_environment(
        engine,
        env_id="env-1",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:aaa",
        status="queued",
        now=now,
    )
    _insert_run(
        engine,
        run_id="run-1",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:aaa",
        status="queued",
        now=now,
    )

    queue = RunQueue(engine, backoff=lambda _attempts: 0)
    claim = queue.claim_next(worker_id="worker-1", now=now, lease_seconds=60)
    assert claim is None

    with engine.begin() as conn:
        conn.execute(
            update(environments)
            .where(environments.c.id == "env-1")
            .values(status="ready")
        )

    claim = queue.claim_next(worker_id="worker-1", now=now, lease_seconds=60)
    assert claim is not None
    assert claim.id == "run-1"
    assert claim.attempt_count == 1

    with engine.begin() as conn:
        row = conn.execute(
            select(runs.c.status, runs.c.claimed_by, runs.c.attempt_count)
            .where(runs.c.id == "run-1")
        ).first()
    assert row is not None
    assert row.status == "running"
    assert row.claimed_by == "worker-1"
    assert row.attempt_count == 1


def test_run_lease_expire_requeues() -> None:
    engine = _engine()
    now = datetime(2025, 1, 10, 12, 0, 0)
    expired_at = now - timedelta(minutes=5)

    _insert_run(
        engine,
        run_id="run-expired",
        workspace_id="ws-2",
        configuration_id="cfg-2",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:bbb",
        status="running",
        now=now,
        attempt_count=1,
        max_attempts=3,
        claim_expires_at=expired_at,
    )

    queue = RunQueue(engine, backoff=lambda _attempts: 5)
    processed = queue.expire_stuck(now=now)
    assert processed == 1

    with engine.begin() as conn:
        row = conn.execute(
            select(
                runs.c.status,
                runs.c.claim_expires_at,
                runs.c.claimed_by,
                runs.c.available_at,
                runs.c.error_message,
                runs.c.completed_at,
            ).where(runs.c.id == "run-expired")
        ).first()
    assert row is not None
    assert row.status == "queued"
    assert row.claimed_by is None
    assert row.claim_expires_at is None
    assert row.completed_at is None
    assert row.error_message == "lease expired"
    assert row.available_at is not None


def test_environment_claim_sets_building() -> None:
    engine = _engine()
    now = datetime(2025, 1, 10, 12, 0, 0)

    _insert_environment(
        engine,
        env_id="env-2",
        workspace_id="ws-3",
        configuration_id="cfg-3",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:ccc",
        status="queued",
        now=now,
    )

    queue = EnvironmentQueue(engine)
    claim = queue.claim_next(worker_id="worker-2", now=now, lease_seconds=120)
    assert claim is not None
    assert claim.id == "env-2"

    with engine.begin() as conn:
        row = conn.execute(
            select(environments.c.status, environments.c.claimed_by)
            .where(environments.c.id == "env-2")
        ).first()
    assert row is not None
    assert row.status == "building"
    assert row.claimed_by == "worker-2"
