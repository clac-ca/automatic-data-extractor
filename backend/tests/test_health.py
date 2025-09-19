"""Tests for the health endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.db import get_sessionmaker
from backend.app.services.documents import ExpiredDocumentPurgeSummary
from backend.app.services.maintenance_status import record_auto_purge_success


def test_health_endpoint_reports_ok_and_creates_sqlite(app_client) -> None:
    """`GET /health` should return status ok and trigger DB creation."""

    client, db_path, documents_dir = app_client

    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert "purge" in payload
    assert db_path.exists()
    assert documents_dir.exists()
    assert documents_dir.is_dir()


def test_health_endpoint_includes_purge_summary_when_present(app_client) -> None:
    """`GET /health` should surface the stored automatic purge summary."""

    client, _, _ = app_client
    session_factory = get_sessionmaker()

    summary = ExpiredDocumentPurgeSummary(
        dry_run=False,
        processed_count=2,
        bytes_reclaimed=4096,
    )
    started_at = datetime.now(timezone.utc).isoformat()
    completed_at = datetime.now(timezone.utc).isoformat()

    with session_factory() as db_session:
        record_auto_purge_success(
            db_session,
            summary=summary,
            started_at=started_at,
            completed_at=completed_at,
            interval_seconds=600,
        )
        db_session.commit()

    response = client.get("/health")
    payload = response.json()
    purge = payload["purge"]

    assert purge is not None
    assert purge["status"] == "succeeded"
    assert purge["processed_count"] == 2
    assert purge["bytes_reclaimed"] == 4096
    assert purge["interval_seconds"] == 600
    assert purge["started_at"] == started_at
    assert purge["completed_at"] == completed_at
    assert purge["error"] is None
    assert "missing_files" not in purge
    assert "recorded_at" in purge
