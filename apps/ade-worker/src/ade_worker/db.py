"""Database helpers (SQLite + SQL Server).

We keep the DB layer intentionally thin:
- create_engine() with safe defaults
- optional schema bootstrapping for local dev
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

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
    # Ensure a driver is present; allow override via querystring.
    query = dict(url.query or {})
    query.setdefault("driver", "ODBC Driver 18 for SQL Server")
    return url.set(query=query)


def create_db_engine(
    database_url: str,
    *,
    sqlite_busy_timeout_ms: int = 30000,
    sqlite_journal_mode: str = "WAL",
    sqlite_synchronous: str = "NORMAL",
) -> Engine:
    url = make_url(database_url)
    backend = url.get_backend_name()

    if backend not in {"sqlite", "mssql"}:
        raise ValueError("Only SQLite and SQL Server are supported.")

    if backend == "sqlite":
        _ensure_sqlite_parent(url)
        engine = create_engine(
            url,
            connect_args={
                "check_same_thread": False,
                "timeout": max(int(sqlite_busy_timeout_ms), 0) / 1000.0,
            },
            pool_pre_ping=True,
        )

        journal_mode = (sqlite_journal_mode or "").strip().upper()
        synchronous = (sqlite_synchronous or "").strip().upper()

        def _set_pragmas(dbapi_conn, _record) -> None:
            cur = dbapi_conn.cursor()
            # Reasonable dev defaults; WAL improves concurrency.
            if journal_mode:
                cur.execute(f"PRAGMA journal_mode={journal_mode}")
            if synchronous:
                cur.execute(f"PRAGMA synchronous={synchronous}")
            if sqlite_busy_timeout_ms >= 0:
                cur.execute(f"PRAGMA busy_timeout={int(sqlite_busy_timeout_ms)}")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        event.listen(engine, "connect", _set_pragmas)
        return engine

    # mssql
    url = _mssql_with_defaults(url)
    return create_engine(url, pool_pre_ping=True)


def assert_tables_exist(engine: Engine, required_tables: Iterable[str]) -> None:
    inspector = inspect(engine)
    missing = [t for t in required_tables if not inspector.has_table(t)]
    if missing:
        raise RuntimeError(
            f"Missing required tables: {', '.join(missing)}. "
            "Run your migrations (or enable ADE_WORKER_AUTO_CREATE_SCHEMA=1 for dev)."
        )


def maybe_create_schema(engine: Engine, *, auto_create: bool, required_tables: Iterable[str], metadata) -> None:
    """Create tables on startup only when explicitly enabled.

    For local SQLite dev this is convenient. For production, migrations should own schema changes.
    """
    if auto_create:
        metadata.create_all(engine, checkfirst=True)
    assert_tables_exist(engine, required_tables)
