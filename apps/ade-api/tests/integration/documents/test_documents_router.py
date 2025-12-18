"""Document router tests."""

from __future__ import annotations

import io
from uuid import UUID

import pytest
from fastapi import UploadFile
from httpx import AsyncClient

from ade_api.common.encoding import json_dumps
from ade_api.features.documents.exceptions import DocumentFileMissingError
from ade_api.features.documents.service import DocumentsService
from ade_api.infra.storage import workspace_documents_root
from ade_api.models import Document, User
from ade_api.settings import Settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_upload_list_download_document(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Full upload flow should persist metadata and serve downloads."""

    member = seed_identity.member
    token, _ = await login(
        async_client,
        email=member.email,
        password=member.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("example.txt", b"hello world", "text/plain")},
        data={"metadata": json_dumps({"source": "tests"})},
    )
    assert upload.status_code == 201, upload.text
    payload = upload.json()
    document_id = payload["id"]
    assert payload["byte_size"] == len(b"hello world")
    assert payload["metadata"] == {"source": "tests"}
    assert payload["tags"] == []

    listing = await async_client.get(f"{workspace_base}/documents", headers=headers)
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 25
    assert payload["has_next"] is False
    assert "total" not in payload
    assert any(item["id"] == document_id for item in payload["items"])
    assert all(isinstance(item.get("tags"), list) for item in payload["items"])

    detail = await async_client.get(f"{workspace_base}/documents/{document_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == document_id

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download", headers=headers
    )
    assert download.status_code == 200
    assert download.content == b"hello world"
    assert download.headers["content-type"].startswith("text/plain")
    assert 'attachment; filename="example.txt"' in download.headers["content-disposition"]


async def test_upload_document_ignores_blank_metadata(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Whitespace-only metadata payloads should be treated as empty objects."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("blank.txt", b"payload", "text/plain")},
        data={"metadata": "   "},
    )

    assert upload.status_code == 201, upload.text
    payload = upload.json()
    assert payload["metadata"] == {}


async def test_upload_document_exceeds_limit_returns_413(
    async_client: AsyncClient,
    seed_identity,
    override_app_settings,
) -> None:
    """Uploading a file larger than the configured limit should fail."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
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
    seed_identity,
    session,
    settings: Settings,
) -> None:
    """Soft deletion should flag the record and remove the stored file."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delete.txt", b"temporary", "text/plain")},
    )
    document_id = upload.json()["id"]

    delete_response = await async_client.request(
        "DELETE",
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    detail = await async_client.get(f"{workspace_base}/documents/{document_id}", headers=headers)
    assert detail.status_code == 404

    row = await session.get(Document, UUID(document_id))
    assert row is not None
    assert row.deleted_at is not None
    stored_uri = row.stored_uri

    stored_path = workspace_documents_root(settings, seed_identity.workspace_id) / stored_uri
    assert not stored_path.exists()


async def test_download_missing_file_returns_404(
    async_client: AsyncClient,
    seed_identity,
    session,
    settings: Settings,
) -> None:
    """Downloading a document with a missing backing file should 404."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("missing.txt", b"payload", "text/plain")},
    )
    payload = upload.json()
    document_id = payload["id"]

    row = await session.get(Document, UUID(document_id))
    assert row is not None
    stored_uri = row.stored_uri

    stored_path = workspace_documents_root(settings, seed_identity.workspace_id) / stored_uri
    assert stored_path.exists()
    stored_path.unlink()

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download",
        headers=headers,
    )
    assert download.status_code == 404
    assert "was not found" in download.text


async def test_list_documents_unknown_param_returns_422(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"unexpected": "value"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"][0]["loc"] == ["query", "unexpected"]
    assert payload["detail"][0]["type"] == "extra_forbidden"


async def test_list_documents_invalid_filter_returns_422(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"status_in": "bogus"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"] == "Invalid status value"


async def test_list_documents_uploader_me_filters(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    owner = seed_identity.workspace_owner
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    member_token, _ = await login(async_client, email=member.email, password=member.password)
    member_headers = {"Authorization": f"Bearer {member_token}"}

    upload_one = await async_client.post(
        f"{workspace_base}/documents",
        headers=member_headers,
        files={"file": ("member.txt", b"member", "text/plain")},
    )
    assert upload_one.status_code == 201, upload_one.text

    owner_token, _ = await login(
        async_client,
        email=owner.email,
        password=owner.password,
    )
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    upload_two = await async_client.post(
        f"{workspace_base}/documents",
        headers=owner_headers,
        files={"file": ("owner.txt", b"owner", "text/plain")},
    )
    assert upload_two.status_code == 201, upload_two.text

    # Re-authenticate as the member for filtering assertions.
    member_token, _ = await login(async_client, email=member.email, password=member.password)
    member_headers = {"Authorization": f"Bearer {member_token}"}

    listing = await async_client.get(
        f"{workspace_base}/documents",
        headers=member_headers,
        params={"uploader": "me"},
    )

    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["name"] == "member.txt"


async def test_stream_document_handles_missing_file_mid_stream(
    seed_identity,
    session,
    settings: Settings,
) -> None:
    """Document streaming should surface a domain error when the file disappears."""

    service = DocumentsService(session=session, settings=settings)
    workspace_id = seed_identity.workspace_id

    member = await session.get(User, seed_identity.member.id)
    assert member is not None

    upload = UploadFile(
        filename="race.txt",
        file=io.BytesIO(b"race"),
    )
    record = await service.create_document(
        workspace_id=workspace_id,
        upload=upload,
        metadata=None,
        expires_at=None,
        actor=member,
    )

    _, stream = await service.stream_document(
        workspace_id=workspace_id,
        document_id=record.id,
    )

    stored_row = await session.get(Document, record.id)
    assert stored_row is not None
    stored_path = workspace_documents_root(settings, workspace_id) / stored_row.stored_uri
    stored_path.unlink()

    with pytest.raises(DocumentFileMissingError):
        async for _ in stream:
            pass


async def test_list_document_sheets_reports_parse_failures(
    async_client: AsyncClient, seed_identity
) -> None:
    """Worksheet listing should distinguish parse errors from missing files."""

    member = seed_identity.member
    token, _ = await login(
        async_client,
        email=member.email,
        password=member.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={
            "file": (
                "broken.xlsx",
                b"not an actual xlsx payload",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    listing = await async_client.get(
        f"{workspace_base}/documents/{document_id}/sheets",
        headers=headers,
    )

    assert listing.status_code == 422
    assert "Worksheet inspection failed" in listing.text
