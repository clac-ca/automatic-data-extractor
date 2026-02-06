"""Document update behavior without concurrency headers."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_document_patch_does_not_require_if_match(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    headers = {"Authorization": f"Bearer {token}"}
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("etag.txt", b"etag", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    response = await async_client.patch(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
        json={"metadata": {"tag": "c"}},
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("ETag") is None
