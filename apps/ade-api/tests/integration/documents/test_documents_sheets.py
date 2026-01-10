"""Document worksheet inspection tests."""

from __future__ import annotations

from uuid import uuid4

import anyio
import pytest
from httpx import AsyncClient

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.models import Document, DocumentSource, DocumentStatus
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_list_document_sheets_ignores_cached_metadata_when_missing(
    async_client: AsyncClient,
    seed_identity,
    session,
) -> None:
    """Missing files should not fall back to cached worksheet metadata."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    document = Document(
        id=generate_uuid7(),
        workspace_id=seed_identity.workspace_id,
        original_filename="cached.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        byte_size=12,
        sha256="deadbeef",
        stored_uri="documents/cached.xlsx",
        attributes={
            "worksheets": [
                {"name": "Cached", "index": 0, "kind": "worksheet", "is_active": True},
            ]
        },
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add(document)
    await anyio.to_thread.run_sync(session.commit)

    listing = await async_client.get(
        f"{workspace_base}/documents/{document.id}/sheets",
        headers=headers,
    )

    assert listing.status_code == 404
    assert "was not found" in listing.text


async def test_list_document_sheets_reports_parse_failures(
    async_client: AsyncClient,
    seed_identity,
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
        "Idempotency-Key": f"idem-{uuid4().hex}",
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
