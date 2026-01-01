"""Concurrency checks for document updates."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_document_patch_requires_if_match(async_client: AsyncClient, seed_identity) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    headers = {"Authorization": f"Bearer {token}"}
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers={**headers, "Idempotency-Key": f"idem-{uuid4().hex}"},
        files={"file": ("etag.txt", b"etag", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    get_response = await async_client.get(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
    )
    assert get_response.status_code == 200
    etag = get_response.headers.get("ETag")
    assert etag

    missing_response = await async_client.patch(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
        json={"metadata": {"tag": "a"}},
    )
    assert missing_response.status_code == 428, missing_response.text
    assert missing_response.json()["type"] == "precondition_required"

    wrong_response = await async_client.patch(
        f"{workspace_base}/documents/{document_id}",
        headers={**headers, "If-Match": 'W/"wrong"'},
        json={"metadata": {"tag": "b"}},
    )
    assert wrong_response.status_code == 412, wrong_response.text
    assert wrong_response.json()["type"] == "precondition_failed"

    ok_response = await async_client.patch(
        f"{workspace_base}/documents/{document_id}",
        headers={**headers, "If-Match": etag},
        json={"metadata": {"tag": "c"}},
    )
    assert ok_response.status_code == 200, ok_response.text
    assert ok_response.headers.get("ETag")
