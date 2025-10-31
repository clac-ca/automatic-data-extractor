"""Migration smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.app.shared.core.config import reload_settings
from backend.app.shared.db.engine import get_engine, render_sync_url, reset_database_state


@pytest.mark.asyncio
async def test_alembic_upgrbackend_app_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Applying migrations on a fresh database should succeed."""

    db_path = tmp_path / "migration.sqlite"
    database_url = f"sqlite+aiosqlite:///{db_path}"

    monkeypatch.setenv("ADE_DATABASE_DSN", database_url)
    reload_settings()
    reset_database_state()

    config = Config(str(Path("alembic.ini")))
    config.set_main_option("sqlalchemy.url", render_sync_url(database_url))
    command.upgrade(config, "head")

    try:
        engine = get_engine()
        async with engine.connect() as connection:
            required_tables = {"configs", "config_versions", "jobs", "workspace_config_states"}
            result = await connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('configs','config_versions','jobs','workspace_config_states')"
                )
            )
            existing = {row[0] for row in result.fetchall()}
            assert required_tables.issubset(existing)

            jobs_columns = await connection.execute(text("PRAGMA table_info('jobs')"))
            job_column_names = {row[1] for row in jobs_columns.fetchall()}
            assert {"config_id", "config_version_id", "artifact_uri", "output_uri"}.issubset(
                job_column_names
            )

            config_columns = await connection.execute(
                text("PRAGMA table_info('configs')")
            )
            config_column_names = {row[1] for row in config_columns.fetchall()}
            assert {"slug", "title", "deleted_at"}.issubset(config_column_names)
    finally:
        with pytest.raises(NotImplementedError):
            command.downgrade(config, "base")
        reset_database_state()
        reload_settings()
