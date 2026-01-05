"""Minimal DB helpers for ade-worker (SQLite + MSSQL)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine, URL, make_url


def _ensure_sqlite_parent(url: URL) -> None:
    db = (url.database or "").strip()
    if not db or db == ":memory:" or db.startswith("file:"):
        return
    path = Path(db)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)


def _mssql_with_defaults(url: URL) -> URL:
    query = dict(url.query or {})
    query.setdefault("driver", "ODBC Driver 18 for SQL Server")
    return url.set(query=query)


def create_db_engine(
    database_url: str,
    *,
    sqlite_busy_timeout_ms: int = 30000,
    sqlite_journal_mode: str | None = None,
    sqlite_synchronous: str | None = None,
) -> Engine:
    url = make_url(database_url)
    backend = url.get_backend_name()
    if backend not in {"sqlite", "mssql"}:
        raise ValueError("Only SQLite and SQL Server are supported for ade-worker.")

    if backend == "sqlite":
        _ensure_sqlite_parent(url)
        engine = create_engine(
            url,
            future=True,
            connect_args={
                "check_same_thread": False,
                "timeout": max(sqlite_busy_timeout_ms, 0) / 1000.0,
            },
        )
        journal_mode = (sqlite_journal_mode or "").strip().upper()
        synchronous = (sqlite_synchronous or "").strip().upper()

        def _set_sqlite_pragmas(dbapi_conn, _record) -> None:
            cursor = dbapi_conn.cursor()
            if journal_mode:
                cursor.execute(f"PRAGMA journal_mode={journal_mode}")
            if synchronous:
                cursor.execute(f"PRAGMA synchronous={synchronous}")
            if sqlite_busy_timeout_ms >= 0:
                cursor.execute(f"PRAGMA busy_timeout={int(sqlite_busy_timeout_ms)}")
            cursor.close()

        event.listen(engine, "connect", _set_sqlite_pragmas)
        return engine

    if backend == "mssql":
        url = _mssql_with_defaults(url)
        return create_engine(url, future=True)

    raise ValueError(f"Unsupported backend: {backend}")


def execute_scalar(conn, stmt) -> Any:
    result = conn.execute(stmt)
    return result.scalar_one_or_none()


def assert_schema_ready(engine: Engine) -> None:
    """Fail fast if the database schema has not been migrated."""

    inspector = inspect(engine)
    if not inspector.has_table("alembic_version"):
        raise RuntimeError(
            "Database schema is not initialized. Run `ade migrate` before starting ade-worker."
        )


__all__ = ["assert_schema_ready", "create_db_engine", "execute_scalar"]
