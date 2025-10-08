"""Document router tests."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app import get_settings
from app.db.session import get_sessionmaker
from app.features.documents.models import Document


pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/auth/session",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get("ade_session")
    assert token, "Session cookie missing"
    return token


async def test_upload_list_download_document(
    async_client: AsyncClient,
    seed_identity: dict[str, object],
) -> None:
    """Full upload flow should persist metadata and serve downloads."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])  # type: ignore[index]
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("example.txt", b"hello world", "text/plain")},
        data={"metadata": json.dumps({"source": "tests"})},
    )
    assert upload.status_code == 201, upload.text
    payload = upload.json()
    document_id = payload["document_id"]
    assert payload["byte_size"] == len(b"hello world")
    assert payload["metadata"] == {"source": "tests"}

    listing = await async_client.get(f"{workspace_base}/documents", headers=headers)
    assert listing.status_code == 200
    records = listing.json()
    assert any(item["document_id"] == document_id for item in records)

    detail = await async_client.get(
        f"{workspace_base}/documents/{document_id}", headers=headers
    )
    assert detail.status_code == 200
    assert detail.json()["document_id"] == document_id

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download", headers=headers
    )
    assert download.status_code == 200
    assert download.content == b"hello world"
    assert download.headers["content-type"].startswith("text/plain")
    assert 'attachment; filename="example.txt"' in download.headers['content-disposition']


async def test_upload_document_exceeds_limit_returns_413(
    async_client: AsyncClient,
    seed_identity: dict[str, object],
    override_app_settings,
) -> None:
    """Uploading a file larger than the configured limit should fail."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])  # type: ignore[index]
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    override_app_settings(storage_upload_max_bytes=8)

    response = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("large.bin", b"abcdefghijk", "application/octet-stream")},
    )

    assert response.status_code == 413
    assert "exceeds the allowed maximum" in response.text


async def test_delete_document_marks_deleted(
    async_client: AsyncClient,
    seed_identity: dict[str, object],
) -> None:
    """Soft deletion should flag the record and remove the stored file."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])  # type: ignore[index]
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delete.txt", b"temporary", "text/plain")},
    )
    document_id = upload.json()["document_id"]

    delete_response = await async_client.request(
        "DELETE",
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    detail = await async_client.get(
        f"{workspace_base}/documents/{document_id}", headers=headers
    )
    assert detail.status_code == 404

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        row = await session.get(Document, document_id)
        assert row is not None
        assert row.deleted_at is not None
        stored_uri = row.stored_uri

    settings = get_settings()
    stored_path = settings.storage_documents_dir / stored_uri
    assert not stored_path.exists()


async def test_download_missing_file_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, object],
) -> None:
    """Downloading a document with a missing backing file should 404."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])  # type: ignore[index]
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("missing.txt", b"payload", "text/plain")},
    )
    payload = upload.json()
    document_id = payload["document_id"]
    stored_uri = payload["stored_uri"]

    settings = get_settings()
    stored_path = settings.storage_documents_dir / stored_uri
    assert stored_path.exists()
    stored_path.unlink()

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download",
        headers=headers,
    )
    assert download.status_code == 404
    assert "was not found" in download.text
