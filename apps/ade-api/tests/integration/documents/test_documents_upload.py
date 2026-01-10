"""Document upload and download router tests."""

from __future__ import annotations

import anyio
import io
from uuid import UUID, uuid4

import openpyxl
import pytest
from httpx import AsyncClient

from ade_api.common.encoding import json_dumps
from ade_api.models import Document
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
        "Idempotency-Key": f"idem-{uuid4().hex}",
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
    assert payload["byteSize"] == len(b"hello world")
    assert payload["metadata"] == {"source": "tests"}
    assert payload["tags"] == []
    assert payload["listRow"]["id"] == document_id

    listing = await async_client.get(f"{workspace_base}/documents", headers=headers)
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["page"] == 1
    assert payload["perPage"] == 50
    assert payload["pageCount"] >= 1
    assert payload["total"] >= 1
    assert "changesCursor" in payload
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
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("blank.txt", b"payload", "text/plain")},
        data={"metadata": "   "},
    )

    assert upload.status_code == 201, upload.text
    payload = upload.json()
    assert payload["metadata"] == {}


async def test_list_documents_rejects_unknown_query_params(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """List endpoints should reject unknown query params."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    response = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"unknown": "1"},
    )

    assert response.status_code == 422


async def test_upload_document_does_not_cache_worksheets(
    async_client: AsyncClient,
    seed_identity,
    session,
) -> None:
    """Uploads should not persist worksheet metadata on document records."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    workbook = openpyxl.Workbook()
    workbook.active.title = "Sheet A"
    payload = io.BytesIO()
    workbook.save(payload)
    workbook.close()

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={
            "file": (
                "example.xlsx",
                payload.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])
    record = await anyio.to_thread.run_sync(session.get, Document, document_id)
    assert record is not None
    assert "worksheets" not in (record.attributes or {})


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
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    override_app_settings(storage_upload_max_bytes=8)

    response = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("large.bin", b"abcdefghijk", "application/octet-stream")},
    )

    assert response.status_code == 413
