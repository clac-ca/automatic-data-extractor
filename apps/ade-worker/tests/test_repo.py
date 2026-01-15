from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import sessionmaker

from ade_worker.repo import Repo
from ade_worker.schema import (
    documents,
    environments,
    install_document_event_triggers,
    metadata,
    run_fields,
    run_metrics,
    run_table_columns,
    runs,
)


def _engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    install_document_event_triggers(engine)
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


def _insert_document(engine, *, document_id: str, workspace_id: str, now: datetime) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(documents).values(
                id=document_id,
                workspace_id=workspace_id,
                original_filename="input.xlsx",
                stored_uri="file:documents/input.xlsx",
                last_run_id=None,
                version=1,
                updated_at=now - timedelta(minutes=1),
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


def test_ensure_environment_rows_unique_by_deps_digest() -> None:
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    repo = Repo(SessionLocal)
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


def test_ensure_environment_rows_requeues_failed_env() -> None:
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    repo = Repo(SessionLocal)
    now = datetime(2025, 1, 10, 12, 0, 0)

    _insert_run(
        engine,
        run_id="run-10",
        workspace_id="ws-10",
        configuration_id="cfg-10",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:xyz",
        now=now,
    )
    _insert_environment(
        engine,
        env_id="env-10",
        workspace_id="ws-10",
        configuration_id="cfg-10",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:xyz",
        status="failed",
        error_message="oops",
        now=now,
    )

    inserted = repo.ensure_environment_rows_for_queued_runs(now=now, limit=None)
    assert inserted == 0

    with engine.begin() as conn:
        row = conn.execute(
            select(environments.c.status, environments.c.error_message)
            .where(environments.c.id == "env-10")
        ).first()

    assert row is not None
    assert row.status == "queued"
    assert row.error_message is None


def test_replace_run_metrics_overwrites() -> None:
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    repo = Repo(SessionLocal)
    now = datetime(2025, 1, 10, 12, 0, 0)

    _insert_run(
        engine,
        run_id="run-4",
        workspace_id="ws-4",
        configuration_id="cfg-4",
        engine_spec="apps/ade-engine",
        deps_digest="sha256:aaa",
        now=now,
    )

    with SessionLocal.begin() as session:
        repo.replace_run_metrics(
            session=session,
            run_id="run-4",
            metrics={
                "evaluation_outcome": "partial",
                "evaluation_findings_total": 2,
                "validation_issues_total": 0,
            },
        )

    with engine.begin() as conn:
        row = conn.execute(select(run_metrics)).mappings().first()
    assert row is not None
    assert row["run_id"] == "run-4"
    assert row["evaluation_outcome"] == "partial"
    assert row["evaluation_findings_total"] == 2

    with SessionLocal.begin() as session:
        repo.replace_run_metrics(
            session=session,
            run_id="run-4",
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


def test_replace_run_fields_is_idempotent() -> None:
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    repo = Repo(SessionLocal)
    now = datetime(2025, 1, 10, 12, 0, 0)

    _insert_run(
        engine,
        run_id="run-5",
        workspace_id="ws-5",
        configuration_id="cfg-5",
        engine_spec="apps/ade-engine",
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
        repo.replace_run_fields(session=session, run_id="run-5", rows=rows)

    with engine.begin() as conn:
        first = conn.execute(select(run_fields)).mappings().all()
    assert len(first) == 2

    with SessionLocal.begin() as session:
        repo.replace_run_fields(
            session=session,
            run_id="run-5",
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


def test_replace_run_table_columns_is_idempotent() -> None:
    engine = _engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    repo = Repo(SessionLocal)
    now = datetime(2025, 1, 10, 12, 0, 0)

    _insert_run(
        engine,
        run_id="run-6",
        workspace_id="ws-6",
        configuration_id="cfg-6",
        engine_spec="apps/ade-engine",
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
        repo.replace_run_table_columns(session=session, run_id="run-6", rows=columns)

    with engine.begin() as conn:
        first = conn.execute(select(run_table_columns)).mappings().all()
    assert len(first) == 1
    assert first[0]["mapped_field"] == "email"

    with SessionLocal.begin() as session:
        repo.replace_run_table_columns(session=session, run_id="run-6", rows=[])

    with engine.begin() as conn:
        second = conn.execute(select(run_table_columns)).mappings().all()
    assert second == []
