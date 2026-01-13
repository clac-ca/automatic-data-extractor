"""
database.py

Standard SQLAlchemy engine + session setup for FastAPI.

Rules:
- Settings are defined ONLY in ade_api.settings.Settings (Pydantic).
- This module does NOT read env vars directly.
- Supports SQLite (dev) and SQL Server/Azure SQL (prod).
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Generator

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from ade_api.common.problem_details import ApiError
from ade_api.core.auth.errors import AuthenticationError, PermissionDeniedError
from ade_api.settings import Settings, get_settings
from .azure_sql_auth import attach_azure_sql_managed_identity


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


def _register_sqlite_datetime_adapter() -> None:
    sqlite3.register_adapter(datetime, lambda value: value.isoformat(" "))


def _create_sqlite_engine(url: URL, settings: Settings) -> Engine:
    _ensure_sqlite_parent_dir(url)
    _register_sqlite_datetime_adapter()
    is_memory = _is_sqlite_memory(url)

    connect_args: dict = {"check_same_thread": False}
    if settings.database_sqlite_begin_mode:
        connect_args["isolation_level"] = settings.database_sqlite_begin_mode

    engine = create_engine(
        url,
        echo=settings.database_echo,
        connect_args=connect_args,
        poolclass=StaticPool if is_memory else NullPool,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute(f"PRAGMA busy_timeout={int(settings.database_sqlite_busy_timeout_ms)}")
            cur.execute(f"PRAGMA journal_mode={settings.database_sqlite_journal_mode}")
            cur.execute(f"PRAGMA synchronous={settings.database_sqlite_synchronous}")
        finally:
            cur.close()

    return engine


def _create_mssql_engine(url: URL, settings: Settings) -> Engine:
    if url.drivername == "mssql":
        url = url.set(drivername="mssql+pyodbc")
    if not url.drivername.startswith("mssql+pyodbc"):
        raise ValueError("For SQL Server, use mssql+pyodbc://... (pyodbc is required).")

    url = _mssql_apply_defaults(url)

    if settings.database_auth_mode == "managed_identity":
        url = url.set(username=None, password=None)
        query = dict(url.query or {})
        for k in list(query.keys()):
            if k.lower() in {"authentication", "trusted_connection"}:
                query.pop(k, None)
        url = url.set(query=query)

    engine = create_engine(
        url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
        fast_executemany=True,
    )

    if settings.database_auth_mode == "managed_identity":
        attach_azure_sql_managed_identity(engine, client_id=settings.database_mi_client_id)

    return engine


def build_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    if not settings.database_url:
        raise ValueError("Settings.database_url is required.")
    url = make_url(settings.database_url)
    backend = url.get_backend_name()

    if backend == "sqlite":
        return _create_sqlite_engine(url, settings)
    if backend == "mssql":
        return _create_mssql_engine(url, settings)

    raise ValueError("Unsupported database backend. Use sqlite:// or mssql+pyodbc://.")


# --- FastAPI integration ----------------------------------------------------


def _resolve_app(app_or_request: FastAPI | Request | WebSocket) -> FastAPI:
    if isinstance(app_or_request, FastAPI):
        return app_or_request
    return app_or_request.app


def init_db(app: FastAPI, settings: Settings | None = None) -> None:
    settings = settings or get_settings()

    engine = build_engine(settings)
    existing_engine = getattr(app.state, "db_engine", None)
    if existing_engine is not None:
        existing_engine.dispose()

    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    app.state.db_engine = engine
    app.state.db_sessionmaker = SessionLocal


def shutdown_db(app: FastAPI) -> None:
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
    return get_sessionmaker_from_app(request)


def get_db(request: Request) -> Generator[Session, None, None]:
    SessionLocal = get_sessionmaker(request)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException as exc:
        session.rollback()
        expected = isinstance(
            exc,
            (HTTPException, RequestValidationError, AuthenticationError, PermissionDeniedError),
        )
        if not expected and isinstance(exc, ApiError) and exc.status_code < 500:
            expected = True
        if not expected:
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
