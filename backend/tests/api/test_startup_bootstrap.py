from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.api.main import create_app
from backend.api.settings import Settings


@pytest.mark.asyncio()
async def test_app_startup_bootstraps_database(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "db" / "app.sqlite"
    data_dir = tmp_path / "data"
    documents_dir = tmp_path / "documents"

    settings = Settings.model_validate(
        {
            "database_url": f"sqlite+aiosqlite:///{database_path}",
            "data_dir": str(data_dir),
            "documents_dir": str(documents_dir),
        }
    )

    app = create_app(settings=settings)

    async with app.router.lifespan_context(app):
        pass

    assert database_path.exists()

    result = await asyncio.to_thread(
        _table_exists,
        database_path,
        "users",
    )
    assert result is True


def _table_exists(database: Path, table_name: str) -> bool:
    import sqlite3

    connection = sqlite3.connect(database)
    try:
        cursor = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        row = cursor.fetchone()
    finally:
        connection.close()
    return row is not None
