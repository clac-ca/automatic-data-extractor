from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.utils import login
pytestmark = pytest.mark.asyncio


async def test_documents_delta_returns_changes_since_token(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    first = await async_client.post(
        f"{workspace_base}/documents",
        headers={**headers, "Idempotency-Key": "idem-delta-one"},
        files={"file": ("delta-first.txt", b"first", "text/plain")},
    )
    assert first.status_code == 201, first.text

    listing = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
    )
    assert listing.status_code == 200, listing.text
    changes_cursor = listing.json()["meta"].get("changesCursor")
    assert changes_cursor is not None

    second = await async_client.post(
        f"{workspace_base}/documents",
        headers={**headers, "Idempotency-Key": "idem-delta-two"},
        files={"file": ("delta-second.txt", b"second", "text/plain")},
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]

    delta = await async_client.get(
        f"{workspace_base}/documents/delta",
        headers=headers,
        params={"since": changes_cursor, "limit": 100},
    )
    assert delta.status_code == 200, delta.text
    payload = delta.json()
    ids = [item["documentId"] for item in payload.get("changes", [])]
    assert second_id in ids


async def test_documents_delta_returns_410_for_expired_token(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    created = await async_client.post(
        f"{workspace_base}/documents",
        headers={**headers, "Idempotency-Key": "idem-delta-old"},
        files={"file": ("delta-old.txt", b"old", "text/plain")},
    )
    assert created.status_code == 201, created.text

    expired_token = "0"
    delta = await async_client.get(
        f"{workspace_base}/documents/delta",
        headers=headers,
        params={"since": expired_token},
    )
    assert delta.status_code == 410, delta.text
