"""Repository helpers for worker database access."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from .schema import document_events, documents, environments, runs


class Repo:
    def __init__(self, engine) -> None:
        self.engine = engine

    def load_environment(self, env_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(environments).where(environments.c.id == env_id)
            ).mappings().first()
        return dict(row) if row else None

    def load_ready_environment_for_run(self, run: dict[str, Any]) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(
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
        with self.engine.begin() as conn:
            row = conn.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        return dict(row) if row else None

    def load_document(self, document_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(
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
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
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
                    conn.execute(insert(environments).values(**env_row))
                    inserted += 1
                except IntegrityError:
                    # Environment already exists (unique key).
                    continue
        return inserted

    def mark_environment_queued(
        self,
        *,
        conn,
        env_id: str,
        now: datetime,
        error_message: str,
    ) -> None:
        conn.execute(
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
        conn,
        env_id: str,
        now: datetime,
        python_interpreter: str | None,
        python_version: str | None,
        engine_version: str | None,
    ) -> None:
        conn.execute(
            update(environments)
            .where(environments.c.id == env_id)
            .values(
                python_interpreter=python_interpreter,
                python_version=python_version,
                engine_version=engine_version,
                updated_at=now,
            )
        )

    def touch_environment_last_used(self, *, conn, env_id: str, now: datetime) -> None:
        conn.execute(
            update(environments)
            .where(environments.c.id == env_id)
            .values(last_used_at=now, updated_at=now)
        )

    def update_document_status(
        self,
        *,
        conn,
        document_id: str,
        status: str,
        now: datetime,
    ) -> int | None:
        row = conn.execute(
            select(documents.c.workspace_id, documents.c.version).where(
                documents.c.id == document_id
            )
        ).mappings().first()
        if not row:
            return None
        version = int(row.get("version") or 0) + 1
        conn.execute(
            update(documents)
            .where(documents.c.id == document_id)
            .values(status=status, updated_at=now, version=version)
        )
        conn.execute(
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
        conn,
        run_id: str,
        completed_at: datetime | None,
        exit_code: int | None,
        output_path: str | None,
        error_message: str | None,
    ) -> None:
        conn.execute(
            update(runs)
            .where(runs.c.id == run_id)
            .values(
                completed_at=completed_at,
                exit_code=exit_code,
                output_path=output_path,
                error_message=error_message,
            )
        )


__all__ = ["Repo"]
