"""
ade_worker.db.database

SQLAlchemy engine + session helpers for the worker.

Rules:
- Settings are defined ONLY in ade_worker.settings.Settings (Pydantic).
- This module does NOT read env vars directly.
- Supports SQL Server/Azure SQL only.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Iterator

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from ade_worker.settings import Settings, get_settings
from .azure_sql_auth import attach_azure_sql_managed_identity


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

    if backend == "mssql":
        return _create_mssql_engine(url, settings)
    raise ValueError("Unsupported database backend. Use mssql+pyodbc://.")


def build_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(SessionLocal: sessionmaker[Session]) -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def assert_tables_exist(
    engine: Engine,
    required_tables: Iterable[str],
    *,
    schema: str | None = None,
) -> None:
    inspector = inspect(engine)
    missing = [t for t in required_tables if not inspector.has_table(t, schema=schema)]
    if missing:
        raise RuntimeError(
            f"Missing required tables: {', '.join(missing)}. "
            "Run migrations via ade-api before starting ade-worker."
        )
