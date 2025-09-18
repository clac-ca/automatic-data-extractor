"""Database utilities."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from . import config

Base = declarative_base()

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_engine_url: str | None = None


def _is_sqlite_memory_url(url: URL) -> bool:
    """Return ``True`` when the URL points at an in-memory SQLite database."""

    database = (url.database or "").strip()
    if database in {"", ":memory:"}:
        return True
    return database.startswith("file::memory:")


def _create_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {"future": True}

    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
        if _is_sqlite_memory_url(url):
            engine_kwargs["poolclass"] = StaticPool

    if connect_args:
        engine_kwargs["connect_args"] = connect_args

    return create_engine(database_url, **engine_kwargs)


def get_engine() -> Engine:
    """Return the configured SQLAlchemy engine.

    The application only works with a single database URL at a time, so
    caching a lone engine is sufficient. When the URL changes (primarily in
    tests that monkeypatch configuration) the previous engine is disposed and
    replaced lazily the next time this function is called.
    """

    global _engine, _engine_url

    database_url = config.get_settings().database_url
    if _engine is None or _engine_url != database_url:
        if _engine is not None:
            _engine.dispose()
        _engine = _create_engine(database_url)
        _engine_url = database_url
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return a ``sessionmaker`` bound to the active engine."""

    global _session_factory

    database_url = config.get_settings().database_url
    if _session_factory is None or _engine_url != database_url:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


def reset_database_state() -> None:
    """Dispose cached database resources.

    Test fixtures swap database URLs between runs. Clearing the cached engine
    and session factory keeps imports stable without leaking connections.
    """

    global _engine, _session_factory, _engine_url

    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _engine_url = None


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for the request lifecycle."""

    session_factory = get_sessionmaker()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


__all__ = [
    "Base",
    "get_engine",
    "get_sessionmaker",
    "reset_database_state",
    "get_db",
]
