from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine, insert, select

from ade_worker.repo import Repo
from ade_worker.schema import environments, metadata, runs


def _engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def _insert_run(
    engine,
    *,
    run_id: str,
    workspace_id: str,
    configuration_id: str,
    engine_spec: str,
    deps_digest: str,
    now: datetime,
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
                status="queued",
                available_at=now - timedelta(minutes=1),
                attempt_count=0,
                max_attempts=3,
                claimed_by=None,
                claim_expires_at=None,
                exit_code=None,
                error_message=None,
                created_at=now - timedelta(minutes=5),
                started_at=None,
                completed_at=None,
            )
        )


def test_ensure_environment_rows_unique_by_deps_digest() -> None:
    engine = _engine()
    repo = Repo(engine)
    now = datetime(2025, 1, 10, 12, 0, 0)

    _insert_run(
        engine,
        run_id="run-1",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:aaa",
        now=now,
    )
    _insert_run(
        engine,
        run_id="run-2",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:bbb",
        now=now,
    )
    _insert_run(
        engine,
        run_id="run-3",
        workspace_id="ws-1",
        configuration_id="cfg-1",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:aaa",
        now=now,
    )

    inserted = repo.ensure_environment_rows_for_queued_runs(now=now, limit=None)
    assert inserted == 2

    inserted_again = repo.ensure_environment_rows_for_queued_runs(now=now, limit=None)
    assert inserted_again == 0

    with engine.begin() as conn:
        rows = conn.execute(select(environments.c.deps_digest)).mappings().all()
    digests = sorted(row["deps_digest"] for row in rows)
    assert digests == ["sha256:aaa", "sha256:bbb"]
