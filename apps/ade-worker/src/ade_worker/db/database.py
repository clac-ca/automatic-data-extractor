"""
ade_worker.db.database

SQLAlchemy engine + session helpers for the worker.

Rules:
- Settings are defined ONLY in ade_worker.settings.Settings (Pydantic).
- This module does NOT read env vars directly.
- Postgres-only (psycopg v3).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Iterator

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from ade_worker.settings import Settings, get_settings
from .azure_postgres_auth import attach_azure_postgres_managed_identity


def _apply_sslrootcert(url: URL, sslrootcert: str | None) -> URL:
    if not sslrootcert:
        return url
    query = dict(url.query or {})
    query["sslrootcert"] = sslrootcert
    return url.set(query=query)


def _create_postgres_engine(url: URL, settings: Settings) -> Engine:
    if url.drivername in {"postgresql", "postgres"}:
        url = url.set(drivername="postgresql+psycopg")
    if not url.drivername.startswith("postgresql+psycopg"):
        raise ValueError("For Postgres, use postgresql+psycopg://... (psycopg is required).")

    url = _apply_sslrootcert(url, settings.database_sslrootcert)

    engine = create_engine(
        url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
    )

    if settings.database_auth_mode == "managed_identity":
        attach_azure_postgres_managed_identity(engine)

    return engine


def build_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    if not settings.database_url:
        raise ValueError("Settings.database_url is required.")
    url = make_url(settings.database_url)
    backend = url.get_backend_name()

    if backend == "postgresql":
        return _create_postgres_engine(url, settings)
    raise ValueError("Unsupported database backend. Use postgresql+psycopg://.")


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
