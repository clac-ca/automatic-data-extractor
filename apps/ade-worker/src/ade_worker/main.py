"""ade-worker entrypoint."""

from __future__ import annotations

import logging

from .db import assert_schema_ready, create_db_engine
from .settings import WorkerSettings
from .worker import Worker


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
    )


def _ensure_runtime_dirs(settings: WorkerSettings) -> None:
    for path in (
        settings.workspaces_dir,
        settings.documents_dir,
        settings.configs_dir,
        settings.runs_dir,
        settings.venvs_dir,
        settings.pip_cache_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    settings = WorkerSettings.load()
    _setup_logging(settings.log_level)
    _ensure_runtime_dirs(settings)

    engine = create_db_engine(
        settings.database_url,
        sqlite_busy_timeout_ms=settings.database_sqlite_busy_timeout_ms,
        sqlite_journal_mode=settings.database_sqlite_journal_mode,
        sqlite_synchronous=settings.database_sqlite_synchronous,
    )
    assert_schema_ready(engine)
    worker = Worker(engine=engine, settings=settings)
    worker.start()


__all__ = ["main"]
