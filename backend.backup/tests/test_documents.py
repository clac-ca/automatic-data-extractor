from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.app.auth.email import canonicalize_email
from backend.app.db import get_sessionmaker
from backend.app.models import Document, User
from backend.app.services.documents import delete_document as delete_document_service
from backend.tests.conftest import DEFAULT_USER_EMAIL


def _upload_document(
    client,
    *,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> dict[str, Any]:
    files = {"file": (filename, io.BytesIO(data), content_type)}
    response = client.post("/documents", files=files)
    assert response.status_code == 201
    return response.json()


def _stored_path(documents_dir: Path, payload: dict[str, Any]) -> Path:
    path = Path(payload["stored_uri"])
    if path.is_absolute():
        return path
    return documents_dir / path


def _delete_document(
    client,
    document_id: str,
    *,
    deleted_by: str,
    delete_reason: str | None = None,
):
    payload = {"deleted_by": deleted_by}
    if delete_reason is not None:
        payload["delete_reason"] = delete_reason
    return client.request("DELETE", f"/documents/{document_id}", json=payload)


def test_upload_document_persists_file_and_metadata(app_client) -> None:
    client, _, documents_dir = app_client
    payload = _upload_document(
        client,
        filename="remittance.pdf",
        data=b"PDF-DATA-123",
        content_type="application/pdf",
    )

    assert len(payload["document_id"]) == 26
    assert payload["original_filename"] == "remittance.pdf"
    assert payload["content_type"] == "application/pdf"
    assert payload["byte_size"] == 12
    assert payload["sha256"].startswith("sha256:")
    assert payload["metadata"] == {}

    stored_path = _stored_path(documents_dir, payload)
    assert Path(payload["stored_uri"]).parts[0] == "uploads"
    assert payload["stored_uri"] == f"uploads/{payload['document_id']}"
    assert not Path(payload["stored_uri"]).is_absolute()
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"PDF-DATA-123"
    assert stored_path.relative_to(documents_dir).as_posix() == payload["stored_uri"]

    created_at = datetime.fromisoformat(payload["created_at"])
    expires_at = datetime.fromisoformat(payload["expires_at"])
    assert expires_at - created_at == timedelta(days=30)


def test_duplicate_upload_creates_new_metadata(app_client) -> None:
    client, _, documents_dir = app_client
    original = _upload_document(client, filename="jan.xlsx", data=b"excel-bytes")

    duplicate = _upload_document(client, filename="feb.xlsx", data=b"excel-bytes")

    assert duplicate["document_id"] != original["document_id"]
    assert duplicate["stored_uri"] != original["stored_uri"]

    first_path = _stored_path(documents_dir, original)
    second_path = _stored_path(documents_dir, duplicate)
    assert first_path.exists()
    assert second_path.exists()
    assert first_path.read_bytes() == b"excel-bytes"
    assert second_path.read_bytes() == b"excel-bytes"


def test_upload_document_accepts_manual_expiration(app_client) -> None:
    client, _, _ = app_client
    manual_expiration = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    files = {"file": ("with-expiry.txt", io.BytesIO(b"data"), "text/plain")}
    response = client.post(
        "/documents",
        files=files,
        data={"expires_at": manual_expiration},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["expires_at"] == manual_expiration


def test_upload_document_accepts_zulu_expiration(app_client) -> None:
    client, _, _ = app_client
    manual_expiration = (
        datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=3)
    )
    zulu_expiration = manual_expiration.isoformat().replace("+00:00", "Z")

    files = {"file": ("with-zulu.txt", io.BytesIO(b"data"), "text/plain")}
    response = client.post(
        "/documents",
        files=files,
        data={"expires_at": zulu_expiration},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["expires_at"] == manual_expiration.isoformat()


def test_upload_document_normalises_expiration_timezone(app_client) -> None:
    client, _, _ = app_client
    target_expiration = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    offset_zone = timezone(timedelta(hours=2))
    override = target_expiration.astimezone(offset_zone).isoformat()

    files = {"file": ("with-offset.txt", io.BytesIO(b"data"), "text/plain")}
    response = client.post(
        "/documents",
        files=files,
        data={"expires_at": override},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["expires_at"] == target_expiration.isoformat()


def test_upload_document_rejects_past_expiration(app_client) -> None:
    client, _, _ = app_client
    past_expiration = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    files = {"file": ("expired.txt", io.BytesIO(b"content"), "text/plain")}
    response = client.post(
        "/documents",
        files=files,
        data={"expires_at": past_expiration},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_expiration"
    assert "future" in detail["message"]


def test_upload_document_rejects_invalid_expiration_format(app_client) -> None:
    client, _, _ = app_client

    files = {"file": ("invalid.txt", io.BytesIO(b"content"), "text/plain")}
    response = client.post(
        "/documents",
        files=files,
        data={"expires_at": "not-a-date"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_expiration"
    assert "ISO 8601" in detail["message"]


def test_list_documents_returns_newest_first(app_client) -> None:
    client, _, _ = app_client
    first = _upload_document(client, filename="alpha.csv", data=b"alpha")
    second = _upload_document(client, filename="beta.csv", data=b"beta-data")

    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()
    assert [item["document_id"] for item in data] == [second["document_id"], first["document_id"]]


def test_get_document_returns_metadata(app_client) -> None:
    client, _, _ = app_client
    payload = _upload_document(client, filename="statement.pdf", data=b"pdf-data")

    response = client.get(f"/documents/{payload['document_id']}")
    assert response.status_code == 200
    assert response.json()["document_id"] == payload["document_id"]


def test_get_document_missing_returns_404(app_client) -> None:
    client, _, _ = app_client
    response = client.get("/documents/doc_missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document 'doc_missing' was not found"


def test_download_document_streams_bytes(app_client) -> None:
    client, _, _ = app_client
    payload = _upload_document(client, filename="q1.pdf", data=b"quarterly")

    response = client.get(f"/documents/{payload['document_id']}/download")
    assert response.status_code == 200
    assert response.content == b"quarterly"
    assert (
        response.headers["content-disposition"]
        == f"attachment; filename=\"{payload['original_filename']}\""
    )
    assert response.headers["content-length"] == str(payload["byte_size"])


def test_download_document_with_unicode_filename_sets_rfc5987_header(
    app_client,
) -> None:
    client, _, _ = app_client
    payload = _upload_document(
        client,
        filename="report 🎨.pdf",
        data=b"paint-bytes",
        content_type="application/pdf",
    )

    response = client.get(f"/documents/{payload['document_id']}/download")
    assert response.status_code == 200
    assert response.content == b"paint-bytes"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "filename*=utf-8''report%20%F0%9F%8E%A8.pdf" in disposition


def test_download_missing_file_returns_404(app_client) -> None:
    client, _, documents_dir = app_client
    payload = _upload_document(client, filename="missing.pdf", data=b"payload")

    stored_path = _stored_path(documents_dir, payload)
    stored_path.unlink()

    response = client.get(f"/documents/{payload['document_id']}/download")
    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == f"Stored file for document '{payload['document_id']}' is missing"
    )


def test_download_document_removed_during_open_returns_404(app_client, monkeypatch) -> None:
    client, _, documents_dir = app_client
    payload = _upload_document(client, filename="race.pdf", data=b"bytes")

    target_path = _stored_path(documents_dir, payload)
    assert target_path.exists()

    original_open = Path.open

    def _failing_open(self, mode="r", *args, **kwargs):
        if self == target_path and "b" in mode:
            raise FileNotFoundError("disappeared")
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _failing_open)

    response = client.get(f"/documents/{payload['document_id']}/download")
    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == f"Stored file for document '{payload['document_id']}' is missing"
    )


def test_upload_document_within_custom_limit_succeeds(
    tmp_path, app_client_factory, monkeypatch
) -> None:
    documents_dir = tmp_path / "documents"
    db_path = tmp_path / "ade.sqlite"
    monkeypatch.setenv("ADE_MAX_UPLOAD_BYTES", str(10))

    with app_client_factory(f"sqlite:///{db_path}", documents_dir) as client:
        payload = _upload_document(
            client,
            filename="tiny.bin",
            data=b"x" * 10,
            content_type="application/octet-stream",
        )

    assert payload["byte_size"] == 10


def test_upload_document_honours_configured_retention_days(
    tmp_path, app_client_factory, monkeypatch
) -> None:
    documents_dir = tmp_path / "documents"
    db_path = tmp_path / "ade.sqlite"
    monkeypatch.setenv("ADE_DEFAULT_DOCUMENT_RETENTION_DAYS", "45")

    with app_client_factory(f"sqlite:///{db_path}", documents_dir) as client:
        payload = _upload_document(
            client,
            filename="configured.bin",
            data=b"c",
            content_type="application/octet-stream",
        )

    created_at = datetime.fromisoformat(payload["created_at"])
    expires_at = datetime.fromisoformat(payload["expires_at"])
    assert expires_at - created_at == timedelta(days=45)


def test_upload_document_over_limit_returns_413(
    tmp_path, app_client_factory, monkeypatch
) -> None:
    documents_dir = tmp_path / "documents"
    db_path = tmp_path / "ade.sqlite"
    monkeypatch.setenv("ADE_MAX_UPLOAD_BYTES", str(10))

    with app_client_factory(f"sqlite:///{db_path}", documents_dir) as client:
        files = {"file": ("too-big.bin", io.BytesIO(b"y" * 11), "application/octet-stream")}
        response = client.post("/documents", files=files)

    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["error"] == "document_too_large"
    assert detail["max_upload_bytes"] == 10
    assert detail["received_bytes"] >= 11
    assert "Uploaded file is" in detail["message"]


def test_delete_document_removes_file_and_marks_metadata(app_client) -> None:
    client, _, documents_dir = app_client
    payload = _upload_document(
        client,
        filename="to-delete.pdf",
        data=b"binary-data",
        content_type="application/pdf",
    )

    stored_path = _stored_path(documents_dir, payload)
    assert stored_path.exists()

    response = _delete_document(
        client,
        payload["document_id"],
        deleted_by="ops@ade.local",
        delete_reason="cleanup",
    )

    assert response.status_code == 200
    deleted = response.json()
    assert deleted["deleted_by"] == "ops@ade.local"
    assert deleted["delete_reason"] == "cleanup"
    deleted_at = datetime.fromisoformat(deleted["deleted_at"])
    assert deleted_at.tzinfo is not None
    assert not stored_path.exists()

    events_response = client.get(f"/documents/{payload['document_id']}/events")
    assert events_response.status_code == 200
    events_payload = events_response.json()
    assert events_payload["total"] == 1
    assert events_payload["limit"] == 50
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
            .one()
        )
    event = events_payload["items"][0]
    assert event["event_type"] == "document.deleted"
    assert event["entity_id"] == payload["document_id"]
    assert event["actor_type"] == "user"
    assert event["actor_id"] == user.user_id
    assert event["actor_label"] == user.email
    assert event["source"] == "api"
    assert event["payload"]["deleted_by"] == "ops@ade.local"
    assert event["payload"]["delete_reason"] == "cleanup"
    assert "missing_before_delete" not in event["payload"]

    list_response = client.get("/documents")
    assert list_response.status_code == 200
    assert all(
        item["document_id"] != payload["document_id"]
        for item in list_response.json()
    )


def test_delete_document_is_idempotent(app_client) -> None:
    client, _, documents_dir = app_client
    payload = _upload_document(
        client,
        filename="idempotent.pdf",
        data=b"repeat",
        content_type="application/pdf",
    )

    first_response = _delete_document(
        client,
        payload["document_id"],
        deleted_by="ops",
        delete_reason="initial pass",
    )
    assert first_response.status_code == 200
    deleted_first = first_response.json()
    deleted_at = deleted_first["deleted_at"]
    assert not _stored_path(documents_dir, payload).exists()

    second_response = _delete_document(
        client,
        payload["document_id"],
        deleted_by="ops",
        delete_reason="second pass",
    )
    assert second_response.status_code == 200
    deleted_second = second_response.json()
    assert deleted_second["deleted_at"] == deleted_at
    assert deleted_second["deleted_by"] == "ops"
    assert deleted_second["delete_reason"] == "initial pass"

    events_response = client.get(f"/documents/{payload['document_id']}/events")
    assert events_response.status_code == 200
    assert events_response.json()["total"] == 1


def test_delete_document_rollback_preserves_file(app_client) -> None:
    client, _, documents_dir = app_client
    payload = _upload_document(
        client,
        filename="rollback.pdf",
        data=b"rollback-bytes",
        content_type="application/pdf",
    )

    stored_path = _stored_path(documents_dir, payload)
    assert stored_path.exists()

    session_factory = get_sessionmaker()
    with session_factory() as db_session:
        with pytest.raises(RuntimeError):
            with db_session.begin():
                delete_document_service(
                    db_session,
                    payload["document_id"],
                    deleted_by="rollback@test",
                    commit=False,
                )
                raise RuntimeError("abort transaction")

    assert stored_path.exists()

    with session_factory() as verify_session:
        refreshed = verify_session.get(Document, payload["document_id"])
        assert refreshed is not None
        assert refreshed.deleted_at is None


def test_update_document_merges_metadata_and_emits_event(app_client) -> None:
    client, _, _ = app_client
    payload = _upload_document(
        client,
        filename="to-update.pdf",
        data=b"payload",
        content_type="application/pdf",
    )

    patch_response = client.patch(
        f"/documents/{payload['document_id']}",
        json={
            "metadata": {"status": "processed", "tags": ["initial"]},
            "event_type": "document.status.updated",
            "actor_type": "service",
            "actor_id": "sync-engine",
            "actor_label": "processor",
            "source": "api",
        },
    )

    assert patch_response.status_code == 200
    updated = patch_response.json()
    assert updated["metadata"] == {"status": "processed", "tags": ["initial"]}

    events_response = client.get(f"/documents/{payload['document_id']}/events")
    assert events_response.status_code == 200
    events_payload = events_response.json()
    assert events_payload["total"] == 1
    event = events_payload["items"][0]
    assert event["event_type"] == "document.status.updated"
    assert event["actor_type"] == "service"
    assert event["actor_id"] == "sync-engine"
    assert event["actor_label"] == "processor"
    assert event["source"] == "api"
    assert event["payload"]["metadata"] == {"status": "processed", "tags": ["initial"]}
    assert event["payload"]["changed_keys"] == ["status", "tags"]


def test_update_document_supports_metadata_removal(app_client) -> None:
    client, _, _ = app_client
    payload = _upload_document(
        client,
        filename="to-remove.pdf",
        data=b"payload",
        content_type="application/pdf",
    )

    first_response = client.patch(
        f"/documents/{payload['document_id']}",
        json={
            "metadata": {"status": "queued"},
            "event_type": "document.status.updated",
            "source": "api",
        },
    )

    assert first_response.status_code == 200

    second_response = client.patch(
        f"/documents/{payload['document_id']}",
        json={
            "metadata": {"status": None},
            "event_type": "document.status.cleared",
            "source": "api",
        },
    )

    assert second_response.status_code == 200
    updated = second_response.json()
    assert "status" not in updated["metadata"]

    filtered = client.get(
        f"/documents/{payload['document_id']}/events",
        params={"event_type": "document.status.cleared"},
    )
    assert filtered.status_code == 200
    payload_events = filtered.json()
    assert payload_events["total"] == 1
    event = payload_events["items"][0]
    assert event["payload"]["removed_keys"] == ["status"]
    assert event["payload"]["changed_keys"] == ["status"]


def test_update_document_defaults_event_type_and_source(app_client) -> None:
    client, _, _ = app_client
    payload = _upload_document(
        client,
        filename="defaults.pdf",
        data=b"payload",
        content_type="application/pdf",
    )

    response = client.patch(
        f"/documents/{payload['document_id']}",
        json={"metadata": {"label": "scanned"}},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["metadata"] == {"label": "scanned"}

    events_response = client.get(f"/documents/{payload['document_id']}/events")
    assert events_response.status_code == 200
    events_payload = events_response.json()
    assert events_payload["total"] == 1
    event = events_payload["items"][0]
    assert event["event_type"] == "document.metadata.updated"
    assert event["source"] == "api"
    assert event["payload"]["metadata"] == {"label": "scanned"}
    assert event["actor_type"] == "user"

    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
            .one()
        )

    assert event["actor_id"] == user.user_id
    assert event["actor_label"] == user.email


def test_document_event_timeline_paginates_and_filters(app_client) -> None:
    client, _, _ = app_client
    payload = _upload_document(
        client,
        filename="timeline.pdf",
        data=b"timeline",
        content_type="application/pdf",
    )

    # Instead of manually creating events, perform document updates that generate events
    base_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    for index in range(3):
        response = client.patch(
            f"/documents/{payload['document_id']}",
            json={
                "metadata": {"index": index},
                "source": "timeline-test",
                "event_type": f"document.test.{index}",
            },
            headers={"X-Test-Occurred-At": (base_time + timedelta(minutes=index)).isoformat()},
        )
        assert response.status_code == 200

    response = client.get(
        f"/documents/{payload['document_id']}/events",
        params={"limit": 2, "source": "timeline-test"},
    )
    assert response.status_code == 200
    timeline = response.json()
    expected_summary = {
        "document_id": payload["document_id"],
        "original_filename": payload["original_filename"],
        "content_type": payload["content_type"],
        "byte_size": payload["byte_size"],
        "sha256": payload["sha256"],
        "expires_at": payload["expires_at"],
        "deleted_at": payload.get("deleted_at"),
        "deleted_by": payload.get("deleted_by"),
        "delete_reason": payload.get("delete_reason"),
    }
    assert timeline["entity"] == expected_summary
    assert timeline["total"] == 3
    assert [item["event_type"] for item in timeline["items"]] == [
        "document.test.2",
        "document.test.1",
    ]

    second_page = client.get(
        f"/documents/{payload['document_id']}/events",
        params={"limit": 2, "offset": 2, "source": "timeline-test"},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["total"] == 3
    assert [item["event_type"] for item in second_payload["items"]] == [
        "document.test.0",
    ]

    filtered = client.get(
        f"/documents/{payload['document_id']}/events",
        params={
            "event_type": "document.test.1",
            "source": "timeline-test",
        },
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["event_type"] == "document.test.1"


def test_document_event_timeline_summary_tracks_updates(app_client) -> None:
    client, _, _ = app_client
    payload = _upload_document(
        client,
        filename="summary-updates.pdf",
        data=b"summary",
        content_type="application/pdf",
    )

    delete_response = _delete_document(
        client,
        payload["document_id"],
        deleted_by="ops@ade.local",
        delete_reason="cleanup",
    )
    assert delete_response.status_code == 200
    deleted_document = delete_response.json()

    timeline = client.get(f"/documents/{payload['document_id']}/events")
    assert timeline.status_code == 200
    timeline_payload = timeline.json()
    assert timeline_payload["total"] == 1
    assert timeline_payload["entity"] == {
        "document_id": deleted_document["document_id"],
        "original_filename": deleted_document["original_filename"],
        "content_type": deleted_document["content_type"],
        "byte_size": deleted_document["byte_size"],
        "sha256": deleted_document["sha256"],
        "expires_at": deleted_document["expires_at"],
        "deleted_at": deleted_document["deleted_at"],
        "deleted_by": deleted_document["deleted_by"],
        "delete_reason": deleted_document["delete_reason"],
    }


def test_document_event_timeline_returns_404_for_missing_document(app_client) -> None:
    client, _, _ = app_client

    response = client.get("/documents/does-not-exist/events")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Document 'does-not-exist' was not found"
    )


def test_delete_document_missing_file_returns_404(app_client) -> None:
    client, _, documents_dir = app_client
    payload = _upload_document(
        client,
        filename="missing-delete.pdf",
        data=b"payload",
        content_type="application/pdf",
    )

    stored_path = _stored_path(documents_dir, payload)
    stored_path.unlink()

    response = _delete_document(
        client,
        payload["document_id"],
        deleted_by="ops",
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == f"Stored file for document '{payload['document_id']}' is missing"
    )


def test_delete_missing_document_returns_404(app_client) -> None:
    client, _, _ = app_client

    response = _delete_document(
        client,
        "doc_missing",
        deleted_by="ops",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document 'doc_missing' was not found"


def test_upload_after_delete_creates_new_record(app_client) -> None:
    client, _, documents_dir = app_client
    original = _upload_document(
        client,
        filename="cycle.pdf",
        data=b"cycle-bytes",
        content_type="application/pdf",
    )

    response = _delete_document(
        client,
        original["document_id"],
        deleted_by="ops",
        delete_reason="rotation",
    )
    assert response.status_code == 200

    replacement = _upload_document(
        client,
        filename="cycle.pdf",
        data=b"cycle-bytes",
        content_type="application/pdf",
    )

    assert replacement["document_id"] != original["document_id"]
    new_path = _stored_path(documents_dir, replacement)
    assert new_path.exists()
