"""Async engine management for ADE."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from ade.settings import Settings, get_settings

_ENGINE: AsyncEngine | None = None
_ENGINE_KEY: tuple[Any, ...] | None = None


def _cache_key(settings: Settings) -> tuple[Any, ...]:
    return (
        settings.database_dsn,
        settings.database_echo,
        settings.database_pool_size,
        settings.database_max_overflow,
        settings.database_pool_timeout,
    )


def is_sqlite_memory_url(url: URL) -> bool:
    database = (url.database or "").strip()
    if not database or database == ":memory:":
        return True
    if database.startswith("file:"):
        query = dict(url.query or {})
        if query.get("mode") == "memory":
            return True
    return False


def ensure_sqlite_database_directory(url: URL) -> None:
    """Ensure a filesystem-backed SQLite database can be created."""

    database = (url.database or "").strip()
    if not database or database == ":memory:" or database.startswith("file:"):
        return
    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


def _create_engine(settings: Settings) -> AsyncEngine:
    url = make_url(settings.database_dsn)
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {
        "echo": settings.database_echo,
        "pool_pre_ping": True,
    }

    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        if is_sqlite_memory_url(url):
            engine_kwargs["poolclass"] = StaticPool
        else:
            engine_kwargs["poolclass"] = NullPool
            ensure_sqlite_database_directory(url)
    else:
        engine_kwargs["pool_size"] = settings.database_pool_size
        engine_kwargs["max_overflow"] = settings.database_max_overflow
        engine_kwargs["pool_timeout"] = settings.database_pool_timeout

    if connect_args:
        engine_kwargs["connect_args"] = connect_args

    engine = create_async_engine(
        url.render_as_string(hide_password=False),
        **engine_kwargs,
    )

    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    return engine


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Return a cached async engine matching the active settings."""

    global _ENGINE, _ENGINE_KEY
    settings = settings or get_settings()
    key = _cache_key(settings)
    if _ENGINE is None or _ENGINE_KEY != key:
        if _ENGINE is not None:
            _ENGINE.sync_engine.dispose()
        _ENGINE = _create_engine(settings)
        _ENGINE_KEY = key
    return _ENGINE


def reset_database_state() -> None:
    """Dispose cached engine and associated session factories."""

    global _ENGINE, _ENGINE_KEY
    if _ENGINE is not None:
        _ENGINE.sync_engine.dispose()
    _ENGINE = None
    _ENGINE_KEY = None

    try:
        from . import session as session_module
    except Exception:
        return

    session_module.reset_session_state()

    try:
        from . import bootstrap as bootstrap_module
    except Exception:
        return

    bootstrap_module.reset_bootstrap_state()


def engine_cache_key(settings: Settings) -> tuple[Any, ...]:
    """Expose the cache key used for engine/session reuse."""

    return _cache_key(settings)


def render_sync_url(database_url: str) -> str:
    """Return a synchronous SQLAlchemy URL for Alembic migrations."""

    url = make_url(database_url)
    driver = url.get_backend_name()
    sync_url = url.set(drivername=driver)
    return sync_url.render_as_string(hide_password=False)


__all__ = [
    "engine_cache_key",
    "ensure_sqlite_database_directory",
    "is_sqlite_memory_url",
    "get_engine",
    "render_sync_url",
    "reset_database_state",
]
