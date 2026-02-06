from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from ade_db.engine import session_scope
from ade_db.schema import (
    configurations,
    metadata,
    run_fields,
    run_metrics,
    run_table_columns,
    runs,
)
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
                content_digest=None,
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
    now: datetime,
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
                status="queued",
                available_at=now - timedelta(minutes=1),
                attempt_count=0,
                max_attempts=3,
                claimed_by=None,
                claim_expires_at=None,
                operation="process",
                exit_code=None,
                error_message=None,
                created_at=now - timedelta(minutes=5),
                started_at=None,
                completed_at=None,
            )
        )


def test_record_configuration_validated_digest_updates_row(engine) -> None:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    workspace_id = _uuid()
    configuration_id = _uuid()
    _ensure_workspace_and_configuration(
        engine,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        now=now,
    )

    with session_scope(session_factory) as session:
        updated = db.record_configuration_validated_digest(
            session,
            configuration_id=configuration_id,
            content_digest="sha256:newdigest",
            now=now,
        )

    assert updated is True

    with engine.begin() as conn:
        row = conn.execute(
            select(configurations.c.content_digest).where(configurations.c.id == configuration_id)
        ).first()
    assert row is not None
    assert row.content_digest == "sha256:newdigest"


def test_record_configuration_validated_digest_returns_false_when_missing(engine) -> None:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2025, 1, 10, 12, 0, 0)
    missing_configuration_id = _uuid()

    with session_scope(session_factory) as session:
        updated = db.record_configuration_validated_digest(
            session,
            configuration_id=missing_configuration_id,
            content_digest="sha256:newdigest",
            now=now,
        )
    assert updated is False


def test_replace_run_metrics_overwrites(engine) -> None:
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
        deps_digest="sha256:aaa",
        now=now,
    )

    with session_scope(session_factory) as session:
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

    with session_scope(session_factory) as session:
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

    with session_scope(session_factory) as session:
        db.replace_run_fields(session, run_id=run_id, rows=rows)

    with engine.begin() as conn:
        first = conn.execute(select(run_fields)).mappings().all()
    assert len(first) == 2

    with session_scope(session_factory) as session:
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

    with session_scope(session_factory) as session:
        db.replace_run_table_columns(session, run_id=run_id, rows=columns)

    with engine.begin() as conn:
        first = conn.execute(select(run_table_columns)).mappings().all()
    assert len(first) == 1
    assert first[0]["mapped_field"] == "email"

    with session_scope(session_factory) as session:
        db.replace_run_table_columns(session, run_id=run_id, rows=[])

    with engine.begin() as conn:
        second = conn.execute(select(run_table_columns)).mappings().all()
    assert second == []
