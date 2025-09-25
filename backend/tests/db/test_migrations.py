"""Migration smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.api.db.engine import get_engine, render_sync_url, reset_database_state
from backend.app import reload_settings


@pytest.mark.asyncio
async def test_alembic_upgrade_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Applying migrations on a fresh database should succeed."""

    db_path = tmp_path / "migration.sqlite"
    database_url = f"sqlite+aiosqlite:///{db_path}"

    monkeypatch.setenv("ADE_DATABASE_URL", database_url)
    reload_settings()
    reset_database_state()

    config = Config(str(Path("alembic.ini")))
    config.set_main_option("sqlalchemy.url", render_sync_url(database_url))
    command.upgrade(config, "head")

    try:
        engine = get_engine()
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT COUNT(1) FROM sqlite_master "
                    "WHERE type='table' AND name='configurations'"
                )
            )
            assert result.scalar_one() == 1
    finally:
        command.downgrade(config, "base")
        reset_database_state()
        reload_settings()
