"""Document worksheet inspection tests."""

from __future__ import annotations

from uuid import uuid4

import anyio
import pytest
from httpx import AsyncClient

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.models import File, FileKind, FileVersion, FileVersionOrigin
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_list_document_sheets_ignores_cached_metadata_when_missing(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    """Missing files should not fall back to cached worksheet metadata."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    file_id = generate_uuid7()
    version_id = generate_uuid7()
    name = "cached.xlsx"
    document = File(
        id=file_id,
        workspace_id=seed_identity.workspace_id,
        kind=FileKind.DOCUMENT,
        doc_no=None,
        name=name,
        name_key=name.casefold(),
        blob_name=f"{seed_identity.workspace_id}/files/{file_id}",
        attributes={
            "worksheets": [
                {"name": "Cached", "index": 0, "kind": "worksheet", "is_active": True},
            ]
        },
        expires_at=utc_now(),
        comment_count=0,
        version=1,
    )
    version = FileVersion(
        id=version_id,
        file_id=file_id,
        version_no=1,
        origin=FileVersionOrigin.UPLOADED,
        created_by_user_id=seed_identity.member.id,
        sha256="deadbeef",
        byte_size=12,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename_at_upload=name,
        blob_version_id="v1",
    )
    document.current_version = version
    document.versions.append(version)
    db_session.add_all([document, version])
    await anyio.to_thread.run_sync(db_session.commit)

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
