"""Tests for the health endpoint."""

from __future__ import annotations

import importlib
import sys

from fastapi.testclient import TestClient


def test_health_endpoint_reports_ok_and_creates_sqlite(tmp_path, monkeypatch) -> None:
    """`GET /health` should return status ok and trigger DB creation."""

    db_path = tmp_path / "ade.sqlite"
    documents_dir = tmp_path / "documents"

    monkeypatch.setenv("ADE_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))

    config = importlib.import_module("backend.app.config")
    config.get_settings.cache_clear()

    for module_name in [
        "backend.app.main",
        "backend.app.routes.health",
        "backend.app.models",
        "backend.app.db",
    ]:
        sys.modules.pop(module_name, None)

    importlib.import_module("backend.app.db")
    importlib.import_module("backend.app.models")
    importlib.import_module("backend.app.routes.health")
    main_module = importlib.import_module("backend.app.main")

    with TestClient(main_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert db_path.exists()
    assert documents_dir.exists()
    assert documents_dir.is_dir()
