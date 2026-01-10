"""Repository helpers for worker database access."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .schema import document_events, documents, environments, run_fields, run_metrics, run_table_columns, runs


class Repo:
    def __init__(self, SessionLocal: sessionmaker[Session]) -> None:
        self._SessionLocal = SessionLocal

    def load_environment(self, env_id: str) -> dict[str, Any] | None:
        with self._SessionLocal() as session:
            row = session.execute(
                select(environments).where(environments.c.id == env_id)
            ).mappings().first()
        return dict(row) if row else None

    def load_ready_environment_for_run(self, run: dict[str, Any]) -> dict[str, Any] | None:
        with self._SessionLocal() as session:
            row = session.execute(
                select(environments).where(
                    environments.c.workspace_id == run["workspace_id"],
                    environments.c.configuration_id == run["configuration_id"],
                    environments.c.engine_spec == run["engine_spec"],
                    environments.c.deps_digest == run["deps_digest"],
                    environments.c.status == "ready",
                )
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

    def ensure_environment_rows_for_queued_runs(self, *, now: datetime, limit: int | None = None) -> int:
        stmt = (
            select(
                runs.c.workspace_id,
                runs.c.configuration_id,
                runs.c.engine_spec,
                runs.c.deps_digest,
            )
            .where(
                runs.c.status == "queued",
                runs.c.available_at <= now,
                runs.c.attempt_count < runs.c.max_attempts,
            )
            .distinct()
        )
        if limit:
            stmt = stmt.limit(limit)

        inserted = 0
        with self._SessionLocal.begin() as session:
            rows = session.execute(stmt).mappings().all()
            for row in rows:
                env_row = {
                    "id": str(uuid4()),
                    "workspace_id": row["workspace_id"],
                    "configuration_id": row["configuration_id"],
                    "engine_spec": row["engine_spec"],
                    "deps_digest": row["deps_digest"],
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
                        inserted += 1
                except IntegrityError:
                    # Environment already exists (unique key). Requeue failed environments.
                    session.execute(
                        update(environments)
                        .where(
                            environments.c.workspace_id == row["workspace_id"],
                            environments.c.configuration_id == row["configuration_id"],
                            environments.c.engine_spec == row["engine_spec"],
                            environments.c.deps_digest == row["deps_digest"],
                            environments.c.status == "failed",
                        )
                        .values(
                            status="queued",
                            error_message=None,
                            claimed_by=None,
                            claim_expires_at=None,
                            updated_at=now,
                        )
                    )
                    continue
        return inserted

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

    def update_document_status(
        self,
        *,
        session: Session,
        document_id: str,
        status: str,
        now: datetime,
    ) -> int | None:
        row = session.execute(
            select(documents.c.workspace_id, documents.c.version).where(
                documents.c.id == document_id
            )
        ).mappings().first()
        if not row:
            return None
        version = int(row.get("version") or 0) + 1
        session.execute(
            update(documents)
            .where(documents.c.id == document_id)
            .values(status=status, updated_at=now, last_run_at=now, version=version)
        )
        session.execute(
            insert(document_events).values(
                workspace_id=row["workspace_id"],
                document_id=document_id,
                event_type="document.changed",
                document_version=version,
                request_id=None,
                client_request_id=None,
                payload=None,
                occurred_at=now,
            )
        )
        return version

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
