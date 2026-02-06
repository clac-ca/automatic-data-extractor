"""Programmatic Alembic runner for ADE migrations."""

from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager, suppress
from importlib import resources
from pathlib import Path
from typing import Any, Iterator

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from ade_api.settings import Settings, get_settings

from .engine import build_engine

__all__ = [
    "alembic_config",
    "migration_lock",
    "run_migrations",
    "run_migrations_async",
    "migration_timeout_seconds",
]

DEFAULT_MIGRATION_TIMEOUT_S = 15.0
MIGRATION_LOCK_KEY = 0xADEDB00  # 183,657,216: stable Postgres advisory lock key.


def _alembic_resource_paths() -> tuple[Path, Path]:
    package = resources.files("ade_db")
    alembic_ini = package / "alembic.ini"
    migrations_dir = package / "migrations"
    return alembic_ini, migrations_dir


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


@contextmanager
def migration_lock(settings: Settings) -> Iterator[None]:
    engine = build_engine(settings)
    try:
        with engine.connect() as base_conn:
            conn = base_conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text("SET statement_timeout = 0"))
            conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
            try:
                yield
            finally:
                with suppress(Exception):
                    conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
    finally:
        engine.dispose()


@contextmanager
def alembic_config(settings: Settings | None = None) -> Iterator[Config]:
    alembic_ini_ref, migrations_ref = _alembic_resource_paths()
    with resources.as_file(alembic_ini_ref) as alembic_ini, resources.as_file(
        migrations_ref
    ) as migrations_dir:
        if not alembic_ini.exists():
            raise FileNotFoundError(f"Alembic config not found at {alembic_ini}")
        if not migrations_dir.exists():
            raise FileNotFoundError(f"Alembic migrations not found at {migrations_dir}")

        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("script_location", str(migrations_dir))
        resolved = settings or get_settings()
        if not resolved.database_url:
            raise ValueError("Settings.database_url is required.")
        alembic_cfg.attributes["settings"] = resolved
        # ConfigParser treats % as interpolation; escape to preserve URL encoding.
        safe_url = str(resolved.database_url).replace("%", "%%")
        alembic_cfg.set_main_option("sqlalchemy.url", safe_url)
        yield alembic_cfg


def run_migrations(settings: Settings | None = None, *, revision: str = "head") -> None:
    resolved = settings or get_settings()
    with migration_lock(resolved):
        with alembic_config(resolved) as alembic_cfg:
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
