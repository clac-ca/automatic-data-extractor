from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


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

    assert payload["original_filename"] == "remittance.pdf"
    assert payload["content_type"] == "application/pdf"
    assert payload["byte_size"] == 12
    assert payload["sha256"].startswith("sha256:")
    assert payload["metadata"] == {}

    stored_path = _stored_path(documents_dir, payload)
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
    assert disposition.startswith('attachment; filename="report.pdf"')
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

    audit_response = client.get(f"/documents/{payload['document_id']}/audit-events")
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert audit_payload["total"] == 1
    assert audit_payload["limit"] == 50
    event = audit_payload["items"][0]
    assert event["event_type"] == "document.deleted"
    assert event["entity_id"] == payload["document_id"]
    assert event["actor_label"] == "ops@ade.local"
    assert event["source"] == "api"
    assert event["payload"]["delete_reason"] == "cleanup"
    assert event["payload"]["missing_before_delete"] is False

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

    audit_response = client.get(f"/documents/{payload['document_id']}/audit-events")
    assert audit_response.status_code == 200
    assert audit_response.json()["total"] == 1


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
