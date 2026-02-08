"""Document deletion tests."""

from __future__ import annotations

from uuid import UUID

import anyio
import pytest
from httpx import AsyncClient

from ade_db.models import File
from ade_api.settings import Settings
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_delete_document_marks_deleted(
    async_client: AsyncClient,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    """Soft deletion should flag the record and remove the stored file."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delete.txt", b"temporary", "text/plain")},
    )
    payload = upload.json()
    document_id = payload["id"]
    delete_response = await async_client.request(
        "DELETE",
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    detail = await async_client.get(f"{workspace_base}/documents/{document_id}", headers=headers)
    assert detail.status_code == 404

    row = await anyio.to_thread.run_sync(db_session.get, File, UUID(document_id))
    assert row is not None
    assert row.deleted_at is not None
    stored_path = settings.documents_dir / row.blob_name
    assert not stored_path.exists()
