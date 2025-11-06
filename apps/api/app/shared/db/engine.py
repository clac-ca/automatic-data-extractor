"""Async engine management for ADE."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from apps.api.app.shared.core.config import PROJECT_ROOT, Settings, get_settings
from sqlalchemy import event
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

API_ROOT = (PROJECT_ROOT / "apps/api").resolve()

_ENGINE: AsyncEngine | None = None
_ENGINE_KEY: tuple[Any, ...] | None = None
_BOOTSTRAP_LOCK = asyncio.Lock()
_BOOTSTRAPPED_URLS: set[str] = set()


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
        session_module = None

    if session_module is not None:
        session_module.reset_session_state()

    reset_bootstrap_state()


def _load_alembic_config() -> Config:
    config_path = API_ROOT / "alembic.ini"
    if not config_path.exists():
        msg = f"Alembic configuration not found at {config_path}"
        raise FileNotFoundError(msg)
    config = Config(str(config_path))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def _upgrade_database(settings: Settings, connection: Connection | None = None) -> None:
    config = _load_alembic_config()
    config.set_main_option("sqlalchemy.url", render_sync_url(settings.database_dsn))
    if connection is not None:
        config.attributes["connection"] = connection
    command.upgrade(config, "head")


def _apply_migrations(settings: Settings) -> None:
    url = make_url(settings.database_dsn)
    if url.get_backend_name() == "sqlite":
        ensure_sqlite_database_directory(url)
    _upgrade_database(settings)


async def ensure_database_ready(settings: Settings | None = None) -> None:
    """Create the database and apply migrations if needed."""

    resolved = settings or get_settings()
    database_url = resolved.database_dsn

    async with _BOOTSTRAP_LOCK:
        if database_url in _BOOTSTRAPPED_URLS:
            return

        url = make_url(database_url)

        if url.get_backend_name() == "sqlite" and is_sqlite_memory_url(url):
            engine = get_engine(resolved)

            async with engine.begin() as connection:
                await connection.run_sync(
                    lambda sync_connection: _upgrade_database(
                        resolved, connection=sync_connection
                    )
                )
        else:
            await asyncio.to_thread(_apply_migrations, resolved)
        _BOOTSTRAPPED_URLS.add(database_url)


def reset_bootstrap_state() -> None:
    """Clear cached bootstrap results (useful for tests)."""

    _BOOTSTRAPPED_URLS.clear()


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
    "ensure_database_ready",
    "ensure_sqlite_database_directory",
    "is_sqlite_memory_url",
    "get_engine",
    "render_sync_url",
    "reset_database_state",
    "reset_bootstrap_state",
]
