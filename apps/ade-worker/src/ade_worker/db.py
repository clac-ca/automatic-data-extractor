"""
db.py — ADE worker database helpers (SQLite + SQL Server)

Keep the DB layer intentionally thin:
- create_db_engine(): create_engine() with safe defaults
- assert_tables_exist(): fail fast if required tables are missing

Notes:
- SQLite is intended for local/dev. WAL + busy_timeout helps, but heavy concurrent writes can still block.
- SQL Server requires mssql+pyodbc and enables fast_executemany for bulk operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy import event, inspect, create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.pool import NullPool, StaticPool


def _ensure_sqlite_parent(url: URL) -> None:
    db = (url.database or "").strip()
    if not db or db == ":memory:" or db.startswith("file:"):
        return

    path = Path(db)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)


def _is_sqlite_memory(url: URL) -> bool:
    db = (url.database or "").strip()
    if not db or db == ":memory:":
        return True
    if db.startswith("file:") and (url.query or {}).get("mode") == "memory":
        return True
    return False


def _normalize_sqlite_journal_mode(value: str) -> str:
    v = (value or "").strip().upper()
    if not v:
        return ""
    allowed = {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
    if v not in allowed:
        raise ValueError(f"Invalid SQLite journal_mode={v!r}. Allowed: {sorted(allowed)}")
    return v


def _normalize_sqlite_synchronous(value: str) -> str:
    v = (value or "").strip().upper()
    if not v:
        return ""
    allowed = {"OFF", "NORMAL", "FULL", "EXTRA", "0", "1", "2", "3"}
    if v not in allowed:
        raise ValueError(f"Invalid SQLite synchronous={v!r}. Allowed: {sorted(allowed)}")
    return v


def _mssql_with_defaults(url: URL) -> URL:
    """Ensure driver + encryption defaults exist; allow overrides via query string (case-insensitive)."""
    query = dict(url.query or {})
    present = {k.lower() for k in query}

    def _setdefault_ci(key: str, value: str) -> None:
        if key.lower() not in present:
            query[key] = value
            present.add(key.lower())

    _setdefault_ci("driver", "ODBC Driver 18 for SQL Server")
    _setdefault_ci("Encrypt", "yes")
    _setdefault_ci("TrustServerCertificate", "no")
    return url.set(query=query)


def create_db_engine(
    database_url: str,
    *,
    echo: bool = False,
    # SQLite tuning (dev)
    sqlite_busy_timeout_ms: int = 30_000,
    sqlite_journal_mode: str = "WAL",
    sqlite_synchronous: str = "NORMAL",
    # SQL Server pooling (prod)
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
) -> Engine:
    """
    Create a SQLAlchemy Engine for SQLite or SQL Server.

    SQLite:
      - file-backed: NullPool (simple)
      - in-memory:  StaticPool
      - PRAGMAs: foreign_keys=ON, busy_timeout, journal_mode, synchronous

    SQL Server:
      - requires mssql+pyodbc
      - pool_pre_ping + pooling + pool_recycle
      - fast_executemany enabled
    """
    url = make_url(database_url)
    backend = url.get_backend_name()

    if backend == "sqlite":
        _ensure_sqlite_parent(url)
        is_memory = _is_sqlite_memory(url)

        journal_mode = _normalize_sqlite_journal_mode(sqlite_journal_mode)
        synchronous = _normalize_sqlite_synchronous(sqlite_synchronous)
        busy_timeout_ms = int(sqlite_busy_timeout_ms)

        engine = create_engine(
            url,
            echo=echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if is_memory else NullPool,
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _record) -> None:
            cur = dbapi_conn.cursor()
            try:
                cur.execute("PRAGMA foreign_keys=ON")
                if busy_timeout_ms >= 0:
                    cur.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
                if journal_mode:
                    cur.execute(f"PRAGMA journal_mode={journal_mode}")
                if synchronous:
                    cur.execute(f"PRAGMA synchronous={synchronous}")
            finally:
                cur.close()

        return engine

    if backend == "mssql":
        # Normalize + enforce pyodbc
        if url.drivername == "mssql":
            url = url.set(drivername="mssql+pyodbc")
        if not url.drivername.startswith("mssql+pyodbc"):
            raise ValueError("SQL Server requires mssql+pyodbc://... (pyodbc).")

        url = _mssql_with_defaults(url)

        return create_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=int(pool_size),
            max_overflow=int(max_overflow),
            pool_timeout=int(pool_timeout),
            pool_recycle=int(pool_recycle),
            fast_executemany=True,
        )

    raise ValueError("Only SQLite and SQL Server are supported (sqlite:// or mssql+pyodbc://).")


def assert_tables_exist(
    engine: Engine,
    required_tables: Iterable[str],
    *,
    schema: str | None = None,
) -> None:
    """Fail fast if required tables are missing."""
    inspector = inspect(engine)
    missing = [t for t in required_tables if not inspector.has_table(t, schema=schema)]
    if missing:
        raise RuntimeError(
            f"Missing required tables: {', '.join(missing)}. "
            "Run migrations via ade-api before starting ade-worker."
        )


__all__ = [
    "create_db_engine",
    "assert_tables_exist",
]
