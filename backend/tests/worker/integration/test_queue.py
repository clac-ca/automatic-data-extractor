from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from ade_db.engine import session_scope
from ade_db.schema import configurations, metadata, runs
from ade_worker import db


def _uuid() -> str:
    return str(uuid4())


workspaces = metadata.tables["workspaces"]


def _ensure_workspace_and_configuration(
    engine,
    *,
    workspace_id: str,
    configuration_id: str,
    now: datetime,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            pg_insert(workspaces)
            .values(
                id=workspace_id,
                name=f"Workspace {workspace_id[:8]}",
                slug=f"ws-{workspace_id}",
                settings={},
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        conn.execute(
            pg_insert(configurations)
            .values(
                id=configuration_id,
                workspace_id=workspace_id,
                display_name="Config A",
                status="draft",
                published_digest=None,
                last_used_at=None,
                activated_at=None,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )


def _insert_run(
    engine,
    *,
    run_id: str,
    workspace_id: str,
    configuration_id: str,
    deps_digest: str,
    status: str,
    now: datetime,
    attempt_count: int = 0,
    max_attempts: int = 3,
    claim_expires_at: datetime | None = None,
    claimed_by: str | None = None,
    input_file_version_id: str | None = None,
) -> None:
    _ensure_workspace_and_configuration(
        engine,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        now=now,
    )
    with engine.begin() as conn:
        conn.execute(
            insert(runs).values(
                id=run_id,
                workspace_id=workspace_id,
                configuration_id=configuration_id,
                input_file_version_id=input_file_version_id,
                output_file_version_id=None,
                input_sheet_names=None,
                run_options=None,
                deps_digest=deps_digest,
                status=status,
                available_at=now - timedelta(minutes=1),
                attempt_count=attempt_count,
                max_attempts=max_attempts,
                claimed_by=claimed_by,
                claim_expires_at=claim_expires_at,
                operation="process",
                exit_code=None,
                error_message=None,
                created_at=now - timedelta(minutes=10),
                started_at=None,
                completed_at=None,
            )
        )


def test_run_claim_does_not_require_ready_environment(engine) -> None:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    workspace_id = _uuid()
    configuration_id = _uuid()
    run_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:aaa",
        status="queued",
        now=now,
    )

    with session_scope(session_factory) as session:
        claims = db.claim_runs(
            session,
            worker_id="worker-1",
            now=now,
            lease_seconds=60,
            limit=1,
        )
    claim = claims[0] if claims else None
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
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
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
        deps_digest="sha256:bbb",
        status="running",
        now=now,
        attempt_count=1,
        max_attempts=3,
        claim_expires_at=expired_at,
    )

    with session_scope(session_factory) as session:
        processed = db.expire_run_leases(
            session,
            now=now,
            backoff_base_seconds=5,
            backoff_max_seconds=5,
        )
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


def test_run_heartbeat_extends_lease(engine) -> None:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    old_expiry = now + timedelta(minutes=1)
    workspace_id = _uuid()
    configuration_id = _uuid()
    run_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:ccc",
        status="running",
        now=now,
        attempt_count=1,
        max_attempts=3,
        claim_expires_at=old_expiry,
        claimed_by="worker-1",
    )

    with session_scope(session_factory) as session:
        ok = db.heartbeat_run(
            session,
            run_id=run_id,
            worker_id="worker-1",
            now=now,
            lease_seconds=300,
        )
    assert ok is True

    with engine.begin() as conn:
        row = conn.execute(
            select(runs.c.claim_expires_at)
            .where(runs.c.id == run_id)
        ).first()
    assert row is not None
    assert row.claim_expires_at is not None
    assert row.claim_expires_at.replace(tzinfo=None) > old_expiry.replace(tzinfo=None)


def test_run_ack_success_marks_succeeded(engine) -> None:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    run_id = _uuid()
    workspace_id = _uuid()
    configuration_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        deps_digest="sha256:ddd",
        status="running",
        now=now,
        attempt_count=1,
        max_attempts=3,
        claim_expires_at=now + timedelta(minutes=5),
        claimed_by="worker-2",
    )

    with session_scope(session_factory) as session:
        ok = db.ack_run_success(
            session,
            run_id=run_id,
            worker_id="worker-2",
            now=now,
        )
    assert ok is True

    with engine.begin() as conn:
        row = conn.execute(
            select(runs.c.status, runs.c.claimed_by, runs.c.completed_at).where(runs.c.id == run_id)
        ).first()
    assert row is not None
    assert row.status == "succeeded"
    assert row.claimed_by is None
    assert row.completed_at is not None


def test_run_ack_failure_requeues(engine) -> None:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
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
        deps_digest="sha256:eee",
        status="running",
        now=now,
        attempt_count=1,
        max_attempts=3,
        claim_expires_at=now + timedelta(minutes=5),
        claimed_by="worker-4",
    )

    with session_scope(session_factory) as session:
        ok = db.ack_run_failure(
            session,
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
