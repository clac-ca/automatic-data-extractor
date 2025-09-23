"""Helper functions for running Alembic migrations."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Literal, Sequence

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import URL, make_url

from . import config
from .db import Base, get_engine

_APP_DIR = Path(__file__).resolve().parent
_MIGRATIONS_PATH = _APP_DIR / "migrations"

logger = logging.getLogger(__name__)

SchemaState = Literal["migrated", "up_to_date", "metadata_created"]


def _cfg(settings: config.Settings) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_PATH))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _is_sqlite_memory(url: URL) -> bool:
    if url.get_backend_name() != "sqlite":
        return False

    database = (url.database or "").strip()
    if database in {"", ":memory:"}:
        return True
    return database.startswith("file::memory:")


def is_up_to_date(settings: config.Settings | None = None) -> bool:
    active_settings = settings or config.get_settings()
    cfg = _cfg(active_settings)
    script = ScriptDirectory.from_config(cfg)
    head_revision = script.get_current_head()

    with get_engine().connect() as conn:
        context = MigrationContext.configure(conn)
        current = context.get_current_revision()
    return current == head_revision


def apply_migrations(settings: config.Settings | None = None) -> None:
    """Upgrade the configured database to the latest schema revision."""

    active_settings = settings or config.get_settings()
    alembic_cfg = _cfg(active_settings)
    command.upgrade(alembic_cfg, "head")


def ensure_schema(settings: config.Settings | None = None) -> SchemaState:
    """Ensure the database schema exists for the configured backend."""

    active_settings = settings or config.get_settings()
    url = make_url(active_settings.database_url)

    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    if _is_sqlite_memory(url):
        from . import models  # noqa: F401

        Base.metadata.create_all(bind=get_engine())
        logger.info("Initialised in-memory SQLite schema without migrations")
        return "metadata_created"

    auto_migrate = active_settings.auto_migrate
    if auto_migrate is None:
        auto_migrate = (
            url.get_backend_name() == "sqlite"
            and url.database not in (None, "", ":memory:")
        )

    if auto_migrate:
        if is_up_to_date(active_settings):
            logger.info("Database schema already current; migrations skipped")
            return "up_to_date"

        apply_migrations(active_settings)
        logger.info("Applied Alembic migrations up to head")
        return "migrated"

    if not is_up_to_date(active_settings):
        raise RuntimeError("Database not up-to-date. Run: alembic upgrade head")

    logger.info("Database schema already current; migrations skipped")
    return "up_to_date"


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for manual migration commands."""

    parser = argparse.ArgumentParser(description="Manage ADE database migrations.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("upgrade", help="Apply all migrations up to head.")
    subparsers.add_parser(
        "ensure", help="Ensure the schema exists (migrations or in-memory fallback)."
    )

    args = parser.parse_args(argv)

    if args.command == "upgrade":
        apply_migrations()
    else:
        ensure_schema()

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI passthrough
    raise SystemExit(main())


__all__ = ["apply_migrations", "ensure_schema", "main", "is_up_to_date", "SchemaState"]
