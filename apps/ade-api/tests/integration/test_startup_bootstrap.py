"""API bootstrap lifecycle tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ade_api.main import create_app
from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


async def test_app_startup_bootstraps_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "data" / "db" / "api.sqlite"
    data_dir = tmp_path / "data"
    workspaces_dir = data_dir / "workspaces"

    monkeypatch.setenv("ADE_DATABASE_URL", f"sqlite:///{database_path}")
    settings = Settings.model_validate({
        "workspaces_dir": str(workspaces_dir),
        "documents_dir": str(workspaces_dir),
        "database_url": f"sqlite:///{database_path}",
    })

    app = create_app(settings=settings)

    with pytest.raises(RuntimeError, match="Database schema is not initialized"):
        async with app.router.lifespan_context(app):
            pass
