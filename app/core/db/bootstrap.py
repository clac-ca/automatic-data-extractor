"""Helpers for preparing the database before serving requests."""

from __future__ import annotations

import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection, make_url

from app.settings import PROJECT_ROOT, Settings, get_settings
from .engine import (
    ensure_sqlite_database_directory,
    get_engine,
    is_sqlite_memory_url,
    render_sync_url,
)

_BOOTSTRAP_LOCK = asyncio.Lock()
_BOOTSTRAPPED_URLS: set[str] = set()


def _load_alembic_config() -> Config:
    config_path = PROJECT_ROOT / "alembic.ini"
    if not config_path.exists():
        msg = f"Alembic configuration not found at {config_path}"
        raise FileNotFoundError(msg)
    return Config(str(config_path))


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


__all__ = ["ensure_database_ready", "reset_bootstrap_state"]
