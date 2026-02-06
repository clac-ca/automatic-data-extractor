"""Document tagging and tag catalog tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_document_tags_replace_and_patch(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("tags.txt", b"tag payload", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    upload_payload = upload.json()
    document_id = upload_payload["id"]

    replace = await async_client.put(
        f"{workspace_base}/documents/{document_id}/tags",
        headers=headers,
        json={"tags": [" Finance ", "Q1   Report", "finance"]},
    )
    assert replace.status_code == 200, replace.text
    replace_payload = replace.json()
    assert replace_payload["tags"] == ["finance", "q1 report"]

    patch = await async_client.patch(
        f"{workspace_base}/documents/{document_id}/tags",
        headers=headers,
        json={"add": ["Priority"], "remove": ["q1 report"]},
    )
    assert patch.status_code == 200, patch.text
    patch_payload = patch.json()
    assert patch_payload["tags"] == ["finance", "priority"]

    patch_again = await async_client.patch(
        f"{workspace_base}/documents/{document_id}/tags",
        headers=headers,
        json={"add": ["Priority"], "remove": ["q1 report"]},
    )
    assert patch_again.status_code == 200, patch_again.text
    patch_again_payload = patch_again.json()
    assert patch_again_payload["tags"] == ["finance", "priority"]

    empty_patch = await async_client.patch(
        f"{workspace_base}/documents/{document_id}/tags",
        headers=headers,
        json={},
    )
    assert empty_patch.status_code == 422


async def test_tag_catalog_counts_and_excludes_deleted(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    upload_one = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("catalog-one.txt", b"one", "text/plain")},
    )
    assert upload_one.status_code == 201, upload_one.text
    upload_one_payload = upload_one.json()
    document_one = upload_one_payload["id"]

    upload_two = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("catalog-two.txt", b"two", "text/plain")},
    )
    assert upload_two.status_code == 201, upload_two.text
    upload_two_payload = upload_two.json()
    document_two = upload_two_payload["id"]

    replace_one = await async_client.put(
        f"{workspace_base}/documents/{document_one}/tags",
        headers=headers,
        json={"tags": ["finance", "priority"]},
    )
    assert replace_one.status_code == 200, replace_one.text

    replace_two = await async_client.put(
        f"{workspace_base}/documents/{document_two}/tags",
        headers=headers,
        json={"tags": ["finance"]},
    )
    assert replace_two.status_code == 200, replace_two.text

    catalog = await async_client.get(
        f"{workspace_base}/documents/tags",
        headers=headers,
        params={"sort": '[{"id":"count","desc":true}]'},
    )
    assert catalog.status_code == 200, catalog.text
    items = catalog.json()["items"]
    assert items[0]["tag"] == "finance"
    assert items[0]["document_count"] == 2
    assert items[1]["tag"] == "priority"
    assert items[1]["document_count"] == 1

    deleted = await async_client.delete(
        f"{workspace_base}/documents/{document_one}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    catalog_after = await async_client.get(
        f"{workspace_base}/documents/tags",
        headers=headers,
    )
    assert catalog_after.status_code == 200, catalog_after.text
    items_after = catalog_after.json()["items"]
    assert items_after == [{"tag": "finance", "document_count": 1}]


async def test_tag_catalog_rejects_short_query(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get(
        f"{workspace_base}/documents/tags",
        headers=headers,
        params={"q": "a"},
    )
    assert response.status_code == 422
