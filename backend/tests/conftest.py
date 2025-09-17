"""Shared testing fixtures."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Tuple

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(tmp_path, monkeypatch) -> Iterator[Tuple[TestClient, Path, Path]]:
    """Return a TestClient bound to an isolated SQLite database."""

    db_path = tmp_path / "ade.sqlite"
    documents_dir = tmp_path / "documents"

    monkeypatch.setenv("ADE_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))

    import backend.app.config as config_module
    from backend.app.config import Settings

    def _get_settings_override() -> Settings:
        return Settings(
            database_url=f"sqlite:///{db_path}",
            documents_dir=documents_dir,
        )

    monkeypatch.setattr(config_module, "get_settings", _get_settings_override)

    modules_to_clear = [
        "backend.app.db",
        "backend.app.models",
        "backend.app.routes.health",
        "backend.app.routes.snapshots",
        "backend.app.services.snapshots",
        "backend.app.main",
    ]
    for module_name in modules_to_clear:
        sys.modules.pop(module_name, None)

    import backend.app.main as main_module

    with TestClient(main_module.app) as client:
        yield client, db_path, documents_dir
