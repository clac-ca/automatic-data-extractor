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
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ade_api.common.problem_details import ApiError
from ade_api.core.auth.errors import AuthenticationError, PermissionDeniedError
from ade_api.settings import Settings, get_settings
from ade_db.engine import build_engine

logger = logging.getLogger(__name__)


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
