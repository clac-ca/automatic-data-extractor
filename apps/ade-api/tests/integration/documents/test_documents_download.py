"""Document download error handling tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import anyio
import pytest
from httpx import AsyncClient

from ade_api.infra.storage import workspace_documents_root
from ade_api.models import Document
from ade_api.settings import Settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


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
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("missing.txt", b"payload", "text/plain")},
    )
    payload = upload.json()
    document_id = payload["id"]

    row = await anyio.to_thread.run_sync(session.get, Document, UUID(document_id))
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
