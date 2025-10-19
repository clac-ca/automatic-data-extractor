"""API bootstrap lifecycle tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ade.platform.config import Settings
from ade.app import create_app


pytestmark = pytest.mark.asyncio


async def test_app_startup_bootstraps_database(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "db" / "ade.sqlite"
    data_dir = tmp_path / "data"
    documents_dir = data_dir / "documents"

    settings = Settings.model_validate(
        {
            "database_dsn": f"sqlite+aiosqlite:///{database_path}",
            "storage_data_dir": str(data_dir),
            "storage_documents_dir": str(documents_dir),
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


def _table_exists(database_path: Path, table_name: str) -> bool:
    import sqlite3

    with sqlite3.connect(database_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None
