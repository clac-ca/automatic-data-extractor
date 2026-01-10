"""Database engine + session factory (SQLite + Azure SQL).

Standard behavior:
- One engine per process (created at app startup)
- One session per request (FastAPI dependency)
- Commit on success, rollback on exception
- SQLite: WAL + busy_timeout + pool_size=1 (serialize access per process)
- Azure SQL: pooled connections + pre-ping + recycle (fast_executemany for pyodbc only)

Managed Identity:
- Uses azure-identity DefaultAzureCredential to fetch an access token
- Injects token using SQL_COPT_SS_ACCESS_TOKEN (ODBC)
"""

from __future__ import annotations

import asyncio
import os
import struct
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import event
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# ---- Optional deps (managed identity) ---------------------------------------
try:
    from azure.identity import DefaultAzureCredential  # type: ignore
except ModuleNotFoundError:
    DefaultAzureCredential = None  # type: ignore[assignment]

from ade_api.settings import Settings

__all__ = [
    "DatabaseAuthMode",
    "SQLiteBeginMode",
    "DatabaseConfig",
    "Database",
    "db",
    "session_scope",
    "get_db_session",
    "build_sync_url",
    "build_async_url",
    "attach_managed_identity",
]

DatabaseAuthMode = Literal["sql_password", "managed_identity"]
SQLiteBeginMode = Literal["DEFERRED", "IMMEDIATE", "EXCLUSIVE"]

_SQL_COPT_SS_ACCESS_TOKEN = 1256
_AZURE_SQL_SCOPE = "https://database.windows.net/.default"


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Minimal, standard DB config.

    Provide a *sync* SQLAlchemy URL in `url`:

    SQLite:
      sqlite:///./data/db/ade.sqlite

    Azure SQL (SQL auth):
      mssql+pyodbc://user:pass@server:1433/db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no

    For runtime, we automatically convert:
      sqlite -> sqlite+aiosqlite
      mssql+pyodbc -> mssql+aioodbc
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
    sqlite_journal_mode: str = "WAL"      # WAL recommended for mixed read/write
    sqlite_synchronous: str = "NORMAL"    # NORMAL is typical WAL perf/durability tradeoff
    sqlite_busy_timeout_ms: int = 30_000
    sqlite_begin_mode: SQLiteBeginMode | None = None

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        """Load config from ADE_* env vars with safe defaults."""
        url = os.getenv("ADE_DATABASE_URL", "sqlite:///./data/db/ade.sqlite")

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

        auth_mode = (os.getenv("ADE_DATABASE_AUTH_MODE") or "sql_password").strip().lower()
        if auth_mode not in {"sql_password", "managed_identity"}:
            raise ValueError("ADE_DATABASE_AUTH_MODE must be 'sql_password' or 'managed_identity'")

        begin_mode = os.getenv("ADE_DATABASE_SQLITE_BEGIN_MODE")
        begin_mode = begin_mode.strip().upper() if begin_mode else None
        if begin_mode and begin_mode not in {"DEFERRED", "IMMEDIATE", "EXCLUSIVE"}:
            raise ValueError("ADE_DATABASE_SQLITE_BEGIN_MODE must be DEFERRED|IMMEDIATE|EXCLUSIVE")

        sqlite_journal_mode = (
            os.getenv("ADE_DATABASE_SQLITE_JOURNAL_MODE") or "WAL"
        ).strip().upper()
        sqlite_synchronous = (
            os.getenv("ADE_DATABASE_SQLITE_SYNCHRONOUS") or "NORMAL"
        ).strip().upper()

        return cls(
            url=url,
            echo=_bool("ADE_DATABASE_ECHO", default=False),
            auth_mode=auth_mode,  # type: ignore[assignment]
            managed_identity_client_id=os.getenv("ADE_DATABASE_MI_CLIENT_ID") or None,
            pool_size=_int("ADE_DATABASE_POOL_SIZE", 5),
            max_overflow=_int("ADE_DATABASE_MAX_OVERFLOW", 10),
            pool_timeout=_int("ADE_DATABASE_POOL_TIMEOUT", 30),
            pool_recycle=_int("ADE_DATABASE_POOL_RECYCLE", 1800),
            sqlite_journal_mode=sqlite_journal_mode,
            sqlite_synchronous=sqlite_synchronous,
            sqlite_busy_timeout_ms=_int("ADE_DATABASE_SQLITE_BUSY_TIMEOUT_MS", 30_000),
            sqlite_begin_mode=begin_mode,  # type: ignore[assignment]
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> DatabaseConfig:
        """Load config from Settings (which reads .env natively)."""
        url = settings.database_url or "sqlite:///./data/db/ade.sqlite"
        sqlite_journal_mode = (settings.database_sqlite_journal_mode or "WAL").strip().upper()
        sqlite_synchronous = (settings.database_sqlite_synchronous or "NORMAL").strip().upper()

        return cls(
            url=url,
            echo=bool(settings.database_echo),
            auth_mode=settings.database_auth_mode,
            managed_identity_client_id=settings.database_mi_client_id,
            pool_size=int(settings.database_pool_size),
            max_overflow=int(settings.database_max_overflow),
            pool_timeout=int(settings.database_pool_timeout),
            sqlite_journal_mode=sqlite_journal_mode,
            sqlite_synchronous=sqlite_synchronous,
            sqlite_busy_timeout_ms=int(settings.database_sqlite_busy_timeout_ms),
            sqlite_begin_mode=settings.database_sqlite_begin_mode,
        )


# ---- URL helpers ------------------------------------------------------------

def _supported_backend(url: URL) -> str:
    backend = url.get_backend_name()
    if backend not in {"sqlite", "mssql"}:
        raise ValueError("Only SQLite and SQL Server (Azure SQL) are supported.")
    return backend


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


def _mssql_with_defaults(url: URL) -> URL:
    # Ensure ODBC driver default (users can override explicitly in URL)
    query = dict(url.query or {})
    query.setdefault("driver", "ODBC Driver 18 for SQL Server")
    return url.set(query=query)


def _sanitize_mssql_for_managed_identity(url: URL) -> URL:
    # Remove username/password from URL for clarity; token will be injected
    url = url._replace(username=None, password=None)

    query = dict(url.query or {})
    # Remove parameters that conflict with token auth
    for k in ("Authentication", "authentication", "Trusted_Connection", "trusted_connection"):
        query.pop(k, None)
    return url.set(query=query)


def _build_engine_kwargs(url: URL, cfg: DatabaseConfig) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "echo": cfg.echo,
        "pool_pre_ping": True,
    }

    backend = _supported_backend(url)
    if backend == "sqlite":
        kwargs["pool_size"] = 1
        kwargs["max_overflow"] = 0
        kwargs["pool_timeout"] = max(1, cfg.pool_timeout)
        kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": cfg.sqlite_busy_timeout_ms / 1000.0,
        }
        if _is_sqlite_memory(url):
            kwargs["poolclass"] = StaticPool
    else:
        kwargs.update(
            pool_size=cfg.pool_size,
            max_overflow=cfg.max_overflow,
            pool_timeout=cfg.pool_timeout,
            pool_recycle=cfg.pool_recycle,
        )
        if url.drivername.startswith("mssql+pyodbc"):
            kwargs["fast_executemany"] = True

    return kwargs


def build_sync_url(cfg: DatabaseConfig) -> str:
    """Return the *sync* SQLAlchemy URL string (for Alembic)."""
    url = make_url(cfg.url)
    backend = _supported_backend(url)

    if backend == "sqlite":
        sync = url.set(drivername="sqlite")
        return sync.render_as_string(hide_password=False)

    # mssql
    drivername = url.drivername
    if drivername.startswith("mssql+aioodbc"):
        url = url.set(drivername="mssql+pyodbc")
    elif drivername == "mssql":
        url = url.set(drivername="mssql+pyodbc")
    elif not drivername.startswith("mssql+pyodbc"):
        raise ValueError("For SQL Server provide mssql+pyodbc://... (sync) or mssql+aioodbc://...")

    url = _mssql_with_defaults(url)
    if cfg.auth_mode == "managed_identity":
        url = _sanitize_mssql_for_managed_identity(url)

    return url.render_as_string(hide_password=False)


def build_async_url(cfg: DatabaseConfig) -> str:
    """Return the *async* SQLAlchemy URL string (for runtime)."""
    url = make_url(cfg.url)
    backend = _supported_backend(url)

    if backend == "sqlite":
        async_url = url.set(drivername="sqlite+aiosqlite")
        return async_url.render_as_string(hide_password=False)

    # mssql
    drivername = url.drivername
    if drivername.startswith("mssql+pyodbc"):
        url = url.set(drivername="mssql+aioodbc")
    elif drivername == "mssql":
        url = url.set(drivername="mssql+aioodbc")
    elif not drivername.startswith("mssql+aioodbc"):
        raise ValueError("For SQL Server provide mssql+pyodbc://... or mssql+aioodbc://...")

    url = _mssql_with_defaults(url)
    if cfg.auth_mode == "managed_identity":
        url = _sanitize_mssql_for_managed_identity(url)

    return url.render_as_string(hide_password=False)


# ---- Managed Identity injection --------------------------------------------

def attach_managed_identity(sync_engine: Engine, *, client_id: str | None) -> None:
    """Attach Azure SQL Managed Identity token injection to a *sync* SQLAlchemy engine."""
    if getattr(sync_engine, "_ade_mi_attached", False):
        return

    if DefaultAzureCredential is None:
        raise RuntimeError(
            "Managed identity requires 'azure-identity'. Install it or set "
            "ADE_DATABASE_AUTH_MODE=sql_password."
        )

    credential = DefaultAzureCredential(managed_identity_client_id=client_id or None)

    def _token_bytes() -> bytes:
        token = credential.get_token(_AZURE_SQL_SCOPE).token
        raw = token.encode("utf-16-le")
        return struct.pack("<I", len(raw)) + raw

    @event.listens_for(sync_engine, "do_connect", insert=True)
    def _inject(_dialect, _conn_rec, _cargs, cparams):
        attrs_before = dict(cparams.pop("attrs_before", {}) or {})
        attrs_before[_SQL_COPT_SS_ACCESS_TOKEN] = _token_bytes()
        cparams["attrs_before"] = attrs_before

        # Defensive cleanup
        for k in ("user", "username", "password"):
            cparams.pop(k, None)
        for k in ("Authentication", "authentication", "Trusted_Connection", "trusted_connection"):
            cparams.pop(k, None)

    sync_engine._ade_mi_attached = True


# ---- Database object --------------------------------------------------------

class Database:
    """Holds the process-wide engine + sessionmaker.

    Call `init(cfg)` once on startup.
    Call `await dispose()` on shutdown.
    """

    def __init__(self) -> None:
        self._cfg: DatabaseConfig | None = None
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call db.init(...) at startup.")
        return self._engine

    @property
    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        if self._sessionmaker is None:
            raise RuntimeError("Database not initialized. Call db.init(...) at startup.")
        return self._sessionmaker

    @property
    def config(self) -> DatabaseConfig:
        if self._cfg is None:
            raise RuntimeError("Database not initialized.")
        return self._cfg

    def init(self, cfg: DatabaseConfig) -> None:
        """Create engine + sessionmaker (idempotent for identical config)."""
        if self._cfg == cfg and self._engine is not None and self._sessionmaker is not None:
            return

        # If re-init with a different config, caller should dispose explicitly.
        self._cfg = cfg

        async_url = build_async_url(cfg)
        url_obj = make_url(async_url)
        backend = _supported_backend(url_obj)

        if backend == "sqlite":
            # Create dir for file-backed DB
            _ensure_sqlite_parent_dir(url_obj)

        engine_kwargs = _build_engine_kwargs(url_obj, cfg)
        engine = create_async_engine(async_url, **engine_kwargs)

        # Managed identity (works for async too; we attach to the underlying sync engine)
        if backend == "mssql" and cfg.auth_mode == "managed_identity":
            attach_managed_identity(engine.sync_engine, client_id=cfg.managed_identity_client_id)

        # SQLite pragmas
        if backend == "sqlite":
            jm = cfg.sqlite_journal_mode
            sync = cfg.sqlite_synchronous
            busy_ms = int(cfg.sqlite_busy_timeout_ms)
            begin_mode = cfg.sqlite_begin_mode

            @event.listens_for(engine.sync_engine, "connect")
            def _sqlite_on_connect(dbapi_conn, _):
                if begin_mode:
                    # SQLAlchemy will call "begin" events; we emit our own BEGIN mode below
                    dbapi_conn.isolation_level = None

                cur = dbapi_conn.cursor()
                try:
                    cur.execute("PRAGMA foreign_keys=ON")
                    cur.execute(f"PRAGMA busy_timeout={busy_ms}")
                    cur.execute(f"PRAGMA journal_mode={jm}")
                    cur.execute(f"PRAGMA synchronous={sync}")
                finally:
                    cur.close()

            if begin_mode:

                @event.listens_for(engine.sync_engine, "begin")
                def _sqlite_begin(conn):
                    conn.exec_driver_sql(f"BEGIN {begin_mode}")

        self._engine = engine
        self._sessionmaker = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
        )

    async def dispose(self) -> None:
        """Dispose engine (call on shutdown)."""
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None
        self._cfg = None


db = Database()


async def close_session(session: AsyncSession) -> None:
    await asyncio.shield(session.close())


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    session = db.sessionmaker()
    try:
        yield session
    finally:
        await close_session(session)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one AsyncSession per request."""
    session = db.sessionmaker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await close_session(session)
