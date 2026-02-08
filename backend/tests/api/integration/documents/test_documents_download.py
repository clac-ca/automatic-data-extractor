"""Document download error handling tests."""

from __future__ import annotations

from uuid import UUID

import anyio
import pytest
from httpx import AsyncClient

from ade_storage import build_storage_adapter
from ade_db.models import File
from ade_api.settings import Settings
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_download_missing_file_returns_404(
    async_client: AsyncClient,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    """Downloading a document with a missing backing file should 404."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("missing.txt", b"payload", "text/plain")},
    )
    payload = upload.json()
    document_id = payload["id"]

    row = await anyio.to_thread.run_sync(db_session.get, File, UUID(document_id))
    assert row is not None
    storage = build_storage_adapter(settings)
    storage.delete(row.blob_name)

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download",
        headers=headers,
    )
    assert download.status_code == 404
    assert "was not found" in download.text
