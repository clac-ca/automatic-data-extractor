"""API bootstrap lifecycle tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ade_api.main import create_app
from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


async def test_app_startup_bootstraps_database(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "db" / "api.sqlite"
    data_dir = tmp_path / "data"
    workspaces_dir = data_dir / "workspaces"

    settings = Settings.model_validate(
        {
            "database_dsn": f"sqlite+aiosqlite:///{database_path}",
            "workspaces_dir": str(workspaces_dir),
            "documents_dir": str(workspaces_dir),
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


async def test_app_startup_syncs_config_templates(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "db" / "api.sqlite"
    data_dir = tmp_path / "data"
    workspaces_dir = data_dir / "workspaces"
    templates_source = tmp_path / "source-templates"
    templates_dest = data_dir / "templates" / "config_packages"

    for name in ("default", "sandbox"):
        manifest_dir = templates_source / name / "src" / "ade_config"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps({"name": f"{name}-template"}),
            encoding="utf-8",
        )

    stale_destination = templates_dest / "default"
    stale_destination.mkdir(parents=True, exist_ok=True)
    (stale_destination / "stale.txt").write_text("old", encoding="utf-8")

    custom_destination = templates_dest / "custom"
    custom_destination.mkdir(parents=True, exist_ok=True)
    (custom_destination / "custom.txt").write_text("keep", encoding="utf-8")

    settings = Settings.model_validate(
        {
            "database_dsn": f"sqlite+aiosqlite:///{database_path}",
            "workspaces_dir": str(workspaces_dir),
            "documents_dir": str(workspaces_dir),
            "config_templates_source_dir": str(templates_source),
            "config_templates_dir": str(templates_dest),
        }
    )

    app = create_app(settings=settings)

    async with app.router.lifespan_context(app):
        pass

    default_manifest = templates_dest / "default" / "src" / "ade_config" / "manifest.json"
    sandbox_manifest = templates_dest / "sandbox" / "src" / "ade_config" / "manifest.json"
    assert default_manifest.exists()
    assert sandbox_manifest.exists()
    # Bundled templates are replaced, custom templates are preserved.
    assert not (templates_dest / "default" / "stale.txt").exists()
    assert (templates_dest / "custom" / "custom.txt").exists()


def _table_exists(database_path: Path, table_name: str) -> bool:
    import sqlite3

    with sqlite3.connect(database_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None
