from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.orm import sessionmaker

from ade_worker import db
from ade_db.schema import (
    environments,
    run_fields,
    run_metrics,
    run_table_columns,
    runs,
)
from .helpers import seed_file_with_version


def _uuid() -> str:
    return str(uuid4())


def _insert_run(
    engine,
    *,
    run_id: str,
    workspace_id: str,
    configuration_id: str,
    engine_spec: str,
    deps_digest: str,
    now: datetime,
    input_file_version_id: str | None = None,
) -> None:
    if not input_file_version_id:
        _, input_file_version_id = seed_file_with_version(
            engine,
            workspace_id=workspace_id,
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
    error_message: str | None = None,
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
                error_message=error_message,
                created_at=now - timedelta(minutes=5),
                updated_at=now - timedelta(minutes=5),
                last_used_at=None,
                python_version=None,
                python_interpreter=None,
                engine_version=None,
            )
        )


def test_get_or_create_environment_inserts_once(engine) -> None:
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
        now=now,
    )

    run = db.load_run(SessionLocal, run_id)
    assert run is not None

    env_first = db.ensure_environment(SessionLocal, run=run, now=now)
    env_second = db.ensure_environment(SessionLocal, run=run, now=now)

    assert env_first is not None
    assert env_second is not None
    assert env_first["id"] == env_second["id"]

    with engine.begin() as conn:
        rows = conn.execute(select(environments.c.id)).mappings().all()
    assert len(rows) == 1


def test_get_or_create_environment_keeps_failed_status(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)

    workspace_id = _uuid()
    configuration_id = _uuid()
    run_id = _uuid()
    env_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:xyz",
        now=now,
    )
    _insert_environment(
        engine,
        env_id=env_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:xyz",
        status="failed",
        error_message="oops",
        now=now,
    )

    run = db.load_run(SessionLocal, run_id)
    assert run is not None

    env = db.ensure_environment(SessionLocal, run=run, now=now)
    assert env is not None
    assert str(env["id"]) == env_id
    assert env["status"] == "failed"


def test_replace_run_metrics_overwrites(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)

    run_id = _uuid()
    workspace_id = _uuid()
    configuration_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:aaa",
        now=now,
    )

    with SessionLocal.begin() as session:
        db.replace_run_metrics(
            session,
            run_id=run_id,
            metrics={
                "evaluation_outcome": "partial",
                "evaluation_findings_total": 2,
                "validation_issues_total": 0,
            },
        )

    with engine.begin() as conn:
        row = conn.execute(select(run_metrics)).mappings().first()
    assert row is not None
    assert str(row["run_id"]) == run_id
    assert row["evaluation_outcome"] == "partial"
    assert row["evaluation_findings_total"] == 2

    with SessionLocal.begin() as session:
        db.replace_run_metrics(
            session,
            run_id=run_id,
            metrics={
                "evaluation_outcome": "succeeded",
                "evaluation_findings_total": 0,
            },
        )

    with engine.begin() as conn:
        rows = conn.execute(select(run_metrics)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["evaluation_outcome"] == "succeeded"
    assert rows[0]["evaluation_findings_total"] == 0


def test_replace_run_fields_is_idempotent(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)

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
        now=now,
    )

    rows = [
        {
            "field": "email",
            "label": "Email",
            "detected": False,
            "best_mapping_score": None,
            "occurrences_tables": 0,
            "occurrences_columns": 0,
        },
        {
            "field": "first_name",
            "label": "First Name",
            "detected": True,
            "best_mapping_score": 1.0,
            "occurrences_tables": 1,
            "occurrences_columns": 1,
        },
    ]

    with SessionLocal.begin() as session:
        db.replace_run_fields(session, run_id=run_id, rows=rows)

    with engine.begin() as conn:
        first = conn.execute(select(run_fields)).mappings().all()
    assert len(first) == 2

    with SessionLocal.begin() as session:
        db.replace_run_fields(
            session,
            run_id=run_id,
            rows=[
                {
                    "field": "last_name",
                    "label": "Last Name",
                    "detected": True,
                    "best_mapping_score": 0.9,
                    "occurrences_tables": 1,
                    "occurrences_columns": 1,
                }
            ],
        )

    with engine.begin() as conn:
        second = conn.execute(select(run_fields)).mappings().all()
    assert len(second) == 1
    assert second[0]["field"] == "last_name"


def test_replace_run_table_columns_is_idempotent(engine) -> None:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)

    run_id = _uuid()
    workspace_id = _uuid()
    configuration_id = _uuid()

    _insert_run(
        engine,
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:ccc",
        now=now,
    )

    columns = [
        {
            "workbook_index": 0,
            "workbook_name": "Book1.xlsx",
            "sheet_index": 0,
            "sheet_name": "Sheet1",
            "table_index": 0,
            "column_index": 0,
            "header_raw": "Email",
            "header_normalized": "email",
            "non_empty_cells": 10,
            "mapping_status": "mapped",
            "mapped_field": "email",
            "mapping_score": 1.0,
            "mapping_method": "classifier",
            "unmapped_reason": None,
        }
    ]

    with SessionLocal.begin() as session:
        db.replace_run_table_columns(session, run_id=run_id, rows=columns)

    with engine.begin() as conn:
        first = conn.execute(select(run_table_columns)).mappings().all()
    assert len(first) == 1
    assert first[0]["mapped_field"] == "email"

    with SessionLocal.begin() as session:
        db.replace_run_table_columns(session, run_id=run_id, rows=[])

    with engine.begin() as conn:
        second = conn.execute(select(run_table_columns)).mappings().all()
    assert second == []
