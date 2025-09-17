"""Tests for the health endpoint."""

from __future__ import annotations


def test_health_endpoint_reports_ok_and_creates_sqlite(app_client) -> None:
    """`GET /health` should return status ok and trigger DB creation."""

    client, db_path, documents_dir = app_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert db_path.exists()
    assert documents_dir.exists()
    assert documents_dir.is_dir()
