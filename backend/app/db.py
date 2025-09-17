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

_engine_cache: dict[str, Engine] = {}
_sessionmaker_cache: dict[str, sessionmaker[Session]] = {}


def _is_sqlite_memory_url(url: URL) -> bool:
    """Return ``True`` when the URL points at an in-memory SQLite database."""

    database = (url.database or "").strip()
    if database in {"", ":memory:"}:
        return True
    if database.startswith("file:"):
        if database.endswith(":memory:"):
            return True
        mode = url.query.get("mode")
        if isinstance(mode, list):
            mode_value = mode[0] if mode else None
        else:
            mode_value = mode
        if isinstance(mode_value, str) and mode_value.lower() == "memory":
            return True
    return False


def _create_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {"future": True}

    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        if _is_sqlite_memory_url(url):
            engine_kwargs["poolclass"] = StaticPool

    if connect_args:
        engine_kwargs["connect_args"] = connect_args

    return create_engine(database_url, **engine_kwargs)


def get_engine() -> Engine:
    """Return an engine configured from the active settings."""

    database_url = config.get_settings().database_url
    engine = _engine_cache.get(database_url)
    if engine is None:
        engine = _create_engine(database_url)
        _engine_cache[database_url] = engine
    return engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return a ``sessionmaker`` bound to the configured engine."""

    database_url = config.get_settings().database_url
    session_factory = _sessionmaker_cache.get(database_url)
    if session_factory is None:
        session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        _sessionmaker_cache[database_url] = session_factory
    return session_factory


def reset_database_state() -> None:
    """Dispose cached engines and session factories.

    Tests override configuration between runs; clearing these caches avoids the
    need for expensive module reloads.
    """

    for engine in _engine_cache.values():
        engine.dispose()
    _engine_cache.clear()
    _sessionmaker_cache.clear()


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
