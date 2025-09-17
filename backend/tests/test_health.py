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

    # Patch get_settings to ensure fresh config per test
    import backend.app.config
    from backend.app.config import Settings
    monkeypatch.setattr(
        backend.app.config,
        "get_settings",
        lambda: Settings(
            ADE_DATABASE_URL=f"sqlite:///{db_path}",
            ADE_DOCUMENTS_DIR=str(documents_dir),
        ),
    )

    import backend.app.main as main_module
    with TestClient(main_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert db_path.exists()
    assert documents_dir.exists()
    assert documents_dir.is_dir()
