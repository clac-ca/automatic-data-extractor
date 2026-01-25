"""Repository helpers for worker database access."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .schema import documents, environments, run_fields, run_metrics, run_table_columns, runs


class Repo:
    def __init__(self, SessionLocal: sessionmaker[Session]) -> None:
        self._SessionLocal = SessionLocal

    def load_environment(self, env_id: str) -> dict[str, Any] | None:
        with self._SessionLocal() as session:
            row = session.execute(
                select(environments).where(environments.c.id == env_id)
            ).mappings().first()
        return dict(row) if row else None

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        with self._SessionLocal() as session:
            row = session.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        return dict(row) if row else None

    def load_document(self, document_id: str) -> dict[str, Any] | None:
        with self._SessionLocal() as session:
            row = session.execute(
                select(documents).where(documents.c.id == document_id)
            ).mappings().first()
        return dict(row) if row else None

    def get_or_create_environment(
        self,
        *,
        session: Session,
        run: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any] | None:
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
        self,
        *,
        session: Session,
        env_id: str,
        now: datetime,
        error_message: str,
    ) -> None:
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
        self,
        *,
        session: Session,
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

    def touch_environment_last_used(self, *, session: Session, env_id: str, now: datetime) -> None:
        session.execute(
            update(environments)
            .where(environments.c.id == env_id)
            .values(last_used_at=now, updated_at=now)
        )

    def record_run_result(
        self,
        *,
        session: Session,
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
        self,
        *,
        session: Session,
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
        self,
        *,
        session: Session,
        run_id: str,
        rows: Sequence[dict[str, Any]],
    ) -> None:
        session.execute(delete(run_fields).where(run_fields.c.run_id == run_id))
        if not rows:
            return
        payload = [dict(row, run_id=run_id) for row in rows]
        session.execute(insert(run_fields), payload)

    def replace_run_table_columns(
        self,
        *,
        session: Session,
        run_id: str,
        rows: Sequence[dict[str, Any]],
    ) -> None:
        session.execute(delete(run_table_columns).where(run_table_columns.c.run_id == run_id))
        if not rows:
            return
        payload = [dict(row, run_id=run_id) for row in rows]
        session.execute(insert(run_table_columns), payload)


__all__ = ["Repo"]
