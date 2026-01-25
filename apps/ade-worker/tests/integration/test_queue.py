from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.orm import sessionmaker

from ade_worker.queue import EnvironmentQueue, RunQueue
from ade_worker.schema import environments, runs


def _uuid() -> str:
    return str(uuid4())


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
    claimed_by: str | None = None,
    claim_expires_at: datetime | None = None,
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
                claimed_by=claimed_by,
                claim_expires_at=claim_expires_at,
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
    claimed_by: str | None = None,
    input_document_id: str | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(runs).values(
                id=run_id,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                input_document_id=input_document_id or _uuid(),
                input_sheet_names=None,
                run_options=None,
                output_path=None,
                engine_spec=engine_spec,
                deps_digest=deps_digest,
                status=status,
                available_at=now - timedelta(minutes=1),
                attempt_count=attempt_count,
                max_attempts=max_attempts,
                claimed_by=claimed_by,
                claim_expires_at=claim_expires_at,
                exit_code=None,
                error_message=None,
                created_at=now - timedelta(minutes=10),
                started_at=None,
                completed_at=None,
            )
        )


def test_run_claim_does_not_require_ready_environment(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    workspace_id = _uuid()
    configuration_id = _uuid()
    run_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:aaa",
        status="queued",
        now=now,
    )

    queue = RunQueue(engine, SessionLocal, backoff_base_seconds=0, backoff_max_seconds=0)
    claim = queue.claim_next(worker_id="worker-1", now=now, lease_seconds=60)
    assert claim is not None
    assert claim.id.lower() == run_id.lower()
    assert claim.attempt_count == 1

    with engine.begin() as conn:
        row = conn.execute(
            select(runs.c.status, runs.c.claimed_by, runs.c.attempt_count)
            .where(runs.c.id == run_id)
        ).first()
    assert row is not None
    assert row.status == "running"
    assert row.claimed_by == "worker-1"
    assert row.attempt_count == 1


def test_run_lease_expire_requeues(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    expired_at = now - timedelta(minutes=5)
    run_id = _uuid()
    workspace_id = _uuid()
    configuration_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:bbb",
        status="running",
        now=now,
        attempt_count=1,
        max_attempts=3,
        claim_expires_at=expired_at,
    )

    queue = RunQueue(engine, SessionLocal, backoff_base_seconds=5, backoff_max_seconds=5)
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
            ).where(runs.c.id == run_id)
        ).first()
    assert row is not None
    assert row.status == "queued"
    assert row.claimed_by is None
    assert row.claim_expires_at is None
    assert row.completed_at is None
    assert row.error_message == "lease expired"
    assert row.available_at is not None


def test_environment_claim_sets_building(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    env_id = _uuid()
    workspace_id = _uuid()
    configuration_id = _uuid()

    _insert_environment(
        engine,
        env_id=env_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:ccc",
        status="queued",
        now=now,
    )

    queue = EnvironmentQueue(engine, SessionLocal)
    claim = queue.claim_for_build(env_id=env_id, worker_id="worker-2", now=now, lease_seconds=120)
    assert claim is not None
    assert claim.id.lower() == env_id.lower()

    with engine.begin() as conn:
        row = conn.execute(
            select(environments.c.status, environments.c.claimed_by)
            .where(environments.c.id == env_id)
        ).first()
    assert row is not None
    assert row.status == "building"
    assert row.claimed_by == "worker-2"


def test_environment_ack_success_clears_claim(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    env_id = _uuid()
    workspace_id = _uuid()
    configuration_id = _uuid()

    _insert_environment(
        engine,
        env_id=env_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:ddd",
        status="building",
        now=now,
        claimed_by="worker-3",
        claim_expires_at=now + timedelta(minutes=5),
    )

    queue = EnvironmentQueue(engine, SessionLocal)
    ok = queue.ack_success(env_id=env_id, worker_id="worker-3", now=now)
    assert ok is True

    with engine.begin() as conn:
        row = conn.execute(
            select(
                environments.c.status,
                environments.c.claimed_by,
                environments.c.claim_expires_at,
            ).where(environments.c.id == env_id)
        ).first()
    assert row is not None
    assert row.status == "ready"
    assert row.claimed_by is None
    assert row.claim_expires_at is None


def test_run_ack_failure_requeues(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    retry_at = now + timedelta(minutes=2)
    run_id = _uuid()
    workspace_id = _uuid()
    configuration_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:eee",
        status="running",
        now=now,
        attempt_count=1,
        max_attempts=3,
        claim_expires_at=now + timedelta(minutes=5),
        claimed_by="worker-4",
    )

    queue = RunQueue(engine, SessionLocal, backoff_base_seconds=0, backoff_max_seconds=0)
    ok = queue.ack_failure(
        run_id=run_id,
        worker_id="worker-4",
        now=now,
        error_message="boom",
        retry_at=retry_at,
    )
    assert ok is True

    with engine.begin() as conn:
        row = conn.execute(
            select(
                runs.c.status,
                runs.c.claimed_by,
                runs.c.claim_expires_at,
                runs.c.available_at,
                runs.c.error_message,
                runs.c.completed_at,
            ).where(runs.c.id == run_id)
        ).first()
    assert row is not None
    assert row.status == "queued"
    assert row.claimed_by is None
    assert row.claim_expires_at is None
    assert row.available_at.replace(tzinfo=None) == retry_at
    assert row.error_message == "boom"
    assert row.completed_at is None


def test_run_release_for_env_requeues(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    retry_at = now + timedelta(seconds=5)
    run_id = _uuid()
    workspace_id = _uuid()
    configuration_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:fff",
        status="running",
        now=now,
        attempt_count=1,
        max_attempts=3,
        claim_expires_at=now + timedelta(minutes=5),
        claimed_by="worker-5",
    )

    queue = RunQueue(engine, SessionLocal, backoff_base_seconds=0, backoff_max_seconds=0)
    ok = queue.release_for_env(
        run_id=run_id,
        worker_id="worker-5",
        retry_at=retry_at,
        error_message="Environment missing on disk",
    )
    assert ok is True

    with engine.begin() as conn:
        row = conn.execute(
            select(
                runs.c.status,
                runs.c.claimed_by,
                runs.c.claim_expires_at,
                runs.c.available_at,
                runs.c.error_message,
                runs.c.completed_at,
                runs.c.attempt_count,
            ).where(runs.c.id == run_id)
        ).first()
    assert row is not None
    assert row.status == "queued"
    assert row.claimed_by is None
    assert row.claim_expires_at is None
    assert row.available_at.replace(tzinfo=None) == retry_at
    assert row.error_message == "Environment missing on disk"
    assert row.completed_at is None
    assert row.attempt_count == 0
