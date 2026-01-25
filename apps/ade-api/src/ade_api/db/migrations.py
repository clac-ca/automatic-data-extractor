"""Programmatic Alembic runner (optional).

Standard best practice is to run migrations as a separate deploy step,
but if you want "migrate on startup" you can call run_migrations()
from a startup hook.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from ade_api.settings import Settings, get_settings

__all__ = [
    "run_migrations",
    "run_migrations_async",
    "default_alembic_ini_path",
    "migration_timeout_seconds",
]

DEFAULT_MIGRATION_TIMEOUT_S = 15.0


def default_alembic_ini_path() -> Path:
    # apps/ade-api/src/ade_api/db/migrations.py -> parents[3] == apps/ade-api
    return Path(__file__).resolve().parents[3] / "alembic.ini"


def migration_timeout_seconds(value: Any | None = None) -> float | None:
    if value is None:
        raw = os.getenv("ADE_DATABASE_MIGRATION_TIMEOUT_S")
        if raw is None or not raw.strip():
            return DEFAULT_MIGRATION_TIMEOUT_S
        value = raw
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("ADE_DATABASE_MIGRATION_TIMEOUT_S must be a number of seconds") from exc
    if timeout <= 0:
        return None
    return timeout


def run_migrations(settings: Settings | None = None, *, revision: str = "head") -> None:
    alembic_ini = default_alembic_ini_path()
    if not alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found at {alembic_ini}")

    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(alembic_ini.parent / "migrations"))
    resolved = settings or get_settings()
    if not resolved.database_url:
        raise ValueError("Settings.database_url is required.")
    # ConfigParser treats % as interpolation; escape to preserve URL encoding.
    safe_url = resolved.database_url.replace("%", "%%")
    alembic_cfg.set_main_option("sqlalchemy.url", safe_url)
    command.upgrade(alembic_cfg, revision)


async def run_migrations_async(
    settings: Settings | None = None,
    *,
    revision: str = "head",
    timeout_seconds: float | None = None,
) -> None:
    timeout = migration_timeout_seconds(timeout_seconds)
    try:
        if timeout is None:
            await asyncio.to_thread(run_migrations, settings, revision=revision)
        else:
            await asyncio.wait_for(
                asyncio.to_thread(run_migrations, settings, revision=revision),
                timeout=timeout,
            )
    except TimeoutError as exc:
        raise RuntimeError(
            f"Alembic migrations exceeded {timeout:.0f}s "
            "(set ADE_DATABASE_MIGRATION_TIMEOUT_S to override)."
        ) from exc
