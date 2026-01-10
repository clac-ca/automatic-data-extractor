"""
database.py

Standard SQLAlchemy engine + session setup for FastAPI.

Targets:
- SQLite (dev): WAL, busy_timeout, foreign_keys, NullPool for file DBs, StaticPool for memory
- Azure SQL / SQL Server (prod): mssql+pyodbc with pooling, pre-ping, recycle, fast_executemany
- Optional Managed Identity (Azure): token injection helper (see azure_sql_auth.py)

Why sync?
- pyodbc is the most common, stable, and performant option for SQL Server in Python.
- This keeps your DB layer simple and conventional.
- In FastAPI, put DB-heavy routes in `def` (sync) endpoints so they run in the threadpool.

Exports:
- Base (DeclarativeBase)
- DatabaseSettings
- build_engine() (for scripts/migrations)
- init_db(app, ...), shutdown_db(app)
- get_db() dependency (one session per request, commit/rollback handled)
- get_engine(app_or_request), get_sessionmaker(request), get_sessionmaker_from_app(app_or_request)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from .azure_sql_auth import attach_azure_sql_managed_identity


DatabaseAuthMode = Literal["sql_password", "managed_identity"]


# --- Naming convention (helps Alembic + keeps constraints consistent) --------
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    metadata = metadata


# --- Settings ---------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """
    Minimal DB settings.

    Environment variables (recommended):
      ADE_DATABASE_URL
      ADE_DATABASE_ECHO
      ADE_DATABASE_AUTH_MODE=sql_password|managed_identity
      ADE_DATABASE_MI_CLIENT_ID (optional)

      ADE_DATABASE_POOL_SIZE
      ADE_DATABASE_MAX_OVERFLOW
      ADE_DATABASE_POOL_TIMEOUT
      ADE_DATABASE_POOL_RECYCLE

      ADE_DATABASE_SQLITE_JOURNAL_MODE (default WAL)
      ADE_DATABASE_SQLITE_SYNCHRONOUS (default NORMAL)
      ADE_DATABASE_SQLITE_BUSY_TIMEOUT_MS (default 30000)
      ADE_DATABASE_SQLITE_BEGIN_MODE (optional: DEFERRED|IMMEDIATE|EXCLUSIVE)

    Examples:

    SQLite (dev):
      sqlite:///./data/db/ade.sqlite

    Azure SQL with SQL auth:
      mssql+pyodbc://user:password@server.database.windows.net:1433/dbname?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no

    Azure SQL with Managed Identity (no user/pass in URL):
      mssql+pyodbc://server.database.windows.net:1433/dbname?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
      and set ADE_DATABASE_AUTH_MODE=managed_identity
    """

    url: str
    echo: bool = False

    # SQL Server auth
    auth_mode: DatabaseAuthMode = "sql_password"
    managed_identity_client_id: str | None = None

    # Pooling (SQL Server)
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800  # seconds

    # SQLite tuning
    sqlite_journal_mode: str = "WAL"
    sqlite_synchronous: str = "NORMAL"
    sqlite_busy_timeout_ms: int = 30_000
    sqlite_begin_mode: str | None = None

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        def _bool(name: str, default: bool = False) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        def _int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if raw is None or not raw.strip():
                return default
            return int(raw)

        url = os.getenv("ADE_DATABASE_URL", "sqlite:///./data/db/ade.sqlite").strip()
        auth_mode = os.getenv("ADE_DATABASE_AUTH_MODE", "sql_password").strip().lower()
        if auth_mode not in {"sql_password", "managed_identity"}:
            raise ValueError("ADE_DATABASE_AUTH_MODE must be 'sql_password' or 'managed_identity'")

        return cls(
            url=url,
            echo=_bool("ADE_DATABASE_ECHO", False),
            auth_mode=auth_mode,  # type: ignore[assignment]
            managed_identity_client_id=os.getenv("ADE_DATABASE_MI_CLIENT_ID") or None,
            pool_size=_int("ADE_DATABASE_POOL_SIZE", 5),
            max_overflow=_int("ADE_DATABASE_MAX_OVERFLOW", 10),
            pool_timeout=_int("ADE_DATABASE_POOL_TIMEOUT", 30),
            pool_recycle=_int("ADE_DATABASE_POOL_RECYCLE", 1800),
            sqlite_journal_mode=(
                os.getenv("ADE_DATABASE_SQLITE_JOURNAL_MODE", "WAL").strip().upper()
            ),
            sqlite_synchronous=(
                os.getenv("ADE_DATABASE_SQLITE_SYNCHRONOUS", "NORMAL").strip().upper()
            ),
            sqlite_busy_timeout_ms=_int("ADE_DATABASE_SQLITE_BUSY_TIMEOUT_MS", 30_000),
            sqlite_begin_mode=(
                os.getenv("ADE_DATABASE_SQLITE_BEGIN_MODE", "").strip().upper() or None
            ),
        )


# --- Internal helpers -------------------------------------------------------

def _is_sqlite_memory(url: URL) -> bool:
    db = (url.database or "").strip()
    if not db or db == ":memory:":
        return True
    if db.startswith("file:") and (url.query or {}).get("mode") == "memory":
        return True
    return False


def _ensure_sqlite_parent_dir(url: URL) -> None:
    db = (url.database or "").strip()
    if not db or db == ":memory:" or db.startswith("file:"):
        return

    path = Path(db)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)


def _mssql_apply_defaults(url: URL) -> URL:
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




def _create_sqlite_engine(url: URL, settings: DatabaseSettings) -> Engine:
    _ensure_sqlite_parent_dir(url)
    is_memory = _is_sqlite_memory(url)

    connect_args = {
        "check_same_thread": False,
    }
    if settings.sqlite_begin_mode:
        # sqlite3 maps isolation_level to "BEGIN {DEFERRED|IMMEDIATE|EXCLUSIVE}".
        connect_args["isolation_level"] = settings.sqlite_begin_mode

    # Keep SQLite simple for dev: no pooling for file-backed DBs.
    # (If you run multiple *processes* against SQLite, you can still hit locks.)
    engine_kwargs: dict = {
        "echo": settings.echo,
        "connect_args": connect_args,
    }

    if is_memory:
        engine_kwargs["poolclass"] = StaticPool
    else:
        engine_kwargs["poolclass"] = NullPool

    engine = create_engine(url, **engine_kwargs)

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute(f"PRAGMA busy_timeout={int(settings.sqlite_busy_timeout_ms)}")
            # These are standard + sane defaults for file-backed dev DBs
            cur.execute(f"PRAGMA journal_mode={settings.sqlite_journal_mode}")
            cur.execute(f"PRAGMA synchronous={settings.sqlite_synchronous}")
        finally:
            cur.close()

    return engine


def _create_mssql_engine(url: URL, settings: DatabaseSettings) -> Engine:
    # Normalize drivername
    if url.drivername == "mssql":
        url = url.set(drivername="mssql+pyodbc")
    if not url.drivername.startswith("mssql+pyodbc"):
        raise ValueError("For SQL Server, use mssql+pyodbc://... (pyodbc is required).")

    url = _mssql_apply_defaults(url)

    # For managed identity, remove user/pass from URL for clarity. Token gets injected at connect time.
    if settings.auth_mode == "managed_identity":
        url = url.set(username=None, password=None)
        query = dict(url.query or {})
        # Remove params that can conflict with access-token auth
        for k in list(query.keys()):
            if k.lower() in {"authentication", "trusted_connection"}:
                query.pop(k, None)
        url = url.set(query=query)

    engine = create_engine(
        url,
        echo=settings.echo,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout,
        pool_recycle=settings.pool_recycle,
        fast_executemany=True,  # big win for bulk inserts/updates with pyodbc
    )

    if settings.auth_mode == "managed_identity":
        attach_azure_sql_managed_identity(engine, client_id=settings.managed_identity_client_id)

    return engine


def _create_engine(settings: DatabaseSettings) -> Engine:
    url = make_url(settings.url)
    backend = url.get_backend_name()

    if backend == "sqlite":
        return _create_sqlite_engine(url, settings)

    if backend == "mssql":
        return _create_mssql_engine(url, settings)

    raise ValueError("Unsupported database backend. Use SQLite or SQL Server (mssql+pyodbc).")


# --- Public API -------------------------------------------------------------

def _resolve_app(app_or_request: FastAPI | Request | WebSocket) -> FastAPI:
    if isinstance(app_or_request, FastAPI):
        return app_or_request
    return app_or_request.app

def build_engine(settings: DatabaseSettings | None = None) -> Engine:
    """Create an Engine without storing it on app.state (scripts/migrations/tests)."""
    settings = settings or DatabaseSettings.from_env()
    return _create_engine(settings)


def init_db(app: FastAPI, settings: DatabaseSettings | None = None) -> None:
    """
    Initialize and store the Engine + SessionLocal on app.state.

    Call once at app startup.
    """
    settings = settings or DatabaseSettings.from_env()

    # Re-init is allowed (useful for tests). Only swap state after engine builds.
    engine = build_engine(settings)
    existing_engine = getattr(app.state, "db_engine", None)
    if existing_engine is not None:
        existing_engine.dispose()
    SessionLocal = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    app.state.db_engine = engine
    app.state.db_sessionmaker = SessionLocal


def shutdown_db(app: FastAPI) -> None:
    """Dispose the Engine stored on app.state. Call on shutdown."""
    engine = getattr(app.state, "db_engine", None)
    if engine is not None:
        engine.dispose()
    app.state.db_engine = None
    app.state.db_sessionmaker = None


def get_engine(app_or_request: FastAPI | Request | WebSocket) -> Engine:
    app = _resolve_app(app_or_request)
    engine = getattr(app.state, "db_engine", None)
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db(app, ...) at startup.")
    return engine


def get_sessionmaker_from_app(
    app_or_request: FastAPI | Request | WebSocket,
) -> sessionmaker[Session]:
    app = _resolve_app(app_or_request)
    SessionLocal = getattr(app.state, "db_sessionmaker", None)
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db(app, ...) at startup.")
    return SessionLocal


def get_sessionmaker(request: Request) -> sessionmaker[Session]:
    """Return the Session factory stored on app.state (FastAPI dependency)."""
    return get_sessionmaker_from_app(request)


def get_db(request: Request) -> Generator[Session, None, None]:
    """
    FastAPI dependency:
    - One Session per request
    - Commit on success, rollback on exception/cancel
    - Always closes the session
    - Avoid for long-lived SSE/WebSocket streams; use per-message sessions instead
    """
    SessionLocal = get_sessionmaker(request)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException as exc:
        session.rollback()
        if not isinstance(exc, (HTTPException, RequestValidationError)):
            logger.warning(
                "db.session.rollback",
                extra={
                    "path": str(request.url.path),
                    "method": request.method,
                },
                exc_info=exc,
            )
        raise
    finally:
        session.close()
