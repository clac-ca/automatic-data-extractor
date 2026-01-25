"""
database.py

Standard SQLAlchemy engine + session setup for FastAPI.

Rules:
- Settings are defined ONLY in ade_api.settings.Settings (Pydantic).
- This module does NOT read env vars directly.
- Postgres-only (psycopg v3).
"""

from __future__ import annotations

import logging
from typing import Generator

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ade_api.common.problem_details import ApiError
from ade_api.core.auth.errors import AuthenticationError, PermissionDeniedError
from ade_api.settings import Settings, get_settings
from .azure_postgres_auth import attach_azure_postgres_managed_identity


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
