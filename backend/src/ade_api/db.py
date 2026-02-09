"""Database helpers for ADE API (Postgres only)."""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import HTTPConnection

from ade_api.common.problem_details import ApiError
from ade_api.core.auth.errors import AuthenticationError, PermissionDeniedError
from ade_api.settings import Settings, get_settings
from ade_db.engine import build_engine

logger = logging.getLogger(__name__)


# --- App lifecycle ----------------------------------------------------------


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

    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.state.db_engine = engine
    app.state.db_sessionmaker = session_factory


def shutdown_db(app: FastAPI) -> None:
    engine = getattr(app.state, "db_engine", None)
    if engine is not None:
        engine.dispose()
    app.state.db_engine = None
    app.state.db_sessionmaker = None


def _get_engine_for_app(app: FastAPI) -> Engine:
    engine = getattr(app.state, "db_engine", None)
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db(app, ...) at startup.")
    return engine


def _get_session_factory_for_app(app: FastAPI) -> sessionmaker[Session]:
    session_factory = getattr(app.state, "db_sessionmaker", None)
    if session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db(app, ...) at startup.")
    return session_factory


def get_session_factory_from_app(app: FastAPI) -> sessionmaker[Session]:
    return _get_session_factory_for_app(app)


def get_engine_from_app(app: FastAPI) -> Engine:
    return _get_engine_for_app(app)


def get_session_factory(conn: HTTPConnection) -> sessionmaker[Session]:
    return _get_session_factory_for_app(conn.app)


def get_engine(conn: HTTPConnection) -> Engine:
    return _get_engine_for_app(conn.app)


# --- Dependencies -----------------------------------------------------------


def _log_unexpected_db_exception(request: Request, exc: BaseException) -> None:
    expected = isinstance(
        exc,
        (HTTPException, RequestValidationError, AuthenticationError, PermissionDeniedError),
    )
    if not expected and isinstance(exc, ApiError) and exc.status_code < 500:
        expected = True
    if expected:
        return
    logger.warning(
        "db.session.rollback",
        extra={
            "path": str(request.url.path),
            "method": request.method,
        },
        exc_info=exc,
    )


def _get_session(request: Request) -> Generator[Session]:
    session_factory = get_session_factory(request)
    session = session_factory()
    try:
        yield session
        if getattr(request.state, "db_force_write", False):
            session.commit()
        else:
            session.rollback()
    except BaseException as exc:
        session.rollback()
        _log_unexpected_db_exception(request, exc)
        raise
    finally:
        session.close()


def get_db_write(
    request: Request,
    session: Annotated[Session, Depends(_get_session)],
) -> Session:
    request.state.db_force_write = True
    return session


def get_db_read(
    _request: Request,
    session: Annotated[Session, Depends(_get_session)],
) -> Session:
    return session


# --- Exports ----------------------------------------------------------------


__all__ = [
    "init_db",
    "shutdown_db",
    "get_db_write",
    "get_db_read",
    "get_engine",
    "get_engine_from_app",
    "get_session_factory",
    "get_session_factory_from_app",
]
