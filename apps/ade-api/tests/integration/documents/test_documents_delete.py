"""Document deletion tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from ade_api.infra.storage import workspace_documents_root
from ade_api.models import Document
from ade_api.settings import Settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


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
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delete.txt", b"temporary", "text/plain")},
    )
    payload = upload.json()
    document_id = payload["id"]
    detail = await async_client.get(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    etag = detail.headers.get("ETag")
    assert etag is not None

    delete_response = await async_client.request(
        "DELETE",
        f"{workspace_base}/documents/{document_id}",
        headers={**headers, "If-Match": etag},
    )
    assert delete_response.status_code == 204, delete_response.text

    detail = await async_client.get(f"{workspace_base}/documents/{document_id}", headers=headers)
    assert detail.status_code == 404

    row = session.get(Document, UUID(document_id))
    assert row is not None
    assert row.deleted_at is not None
    stored_uri = row.stored_uri

    stored_path = workspace_documents_root(settings, seed_identity.workspace_id) / stored_uri
    assert not stored_path.exists()
