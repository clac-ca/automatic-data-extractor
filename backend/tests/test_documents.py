from __future__ import annotations

import io
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

    relative = stored_path.relative_to(documents_dir)
    digest = payload["sha256"].split(":", 1)[1]
    assert relative.parts[0] == digest[:2]
    assert relative.parts[1] == digest[2:4]
    assert relative.parts[2] == digest


def test_duplicate_upload_reuses_existing_metadata(app_client) -> None:
    client, _, documents_dir = app_client
    original = _upload_document(client, filename="jan.xlsx", data=b"excel-bytes")

    stored_path = _stored_path(documents_dir, original)
    duplicate = _upload_document(client, filename="feb.xlsx", data=b"excel-bytes")

    assert duplicate["document_id"] == original["document_id"]
    assert duplicate["stored_uri"] == original["stored_uri"]
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"excel-bytes"

    # Delete the stored file and upload again to ensure the record is rehydrated.
    stored_path.unlink()
    restored = _upload_document(client, filename="mar.xlsx", data=b"excel-bytes")
    assert restored["document_id"] == original["document_id"]
    assert _stored_path(documents_dir, restored).exists()


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
