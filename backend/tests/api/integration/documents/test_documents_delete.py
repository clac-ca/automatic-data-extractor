"""Document deletion tests."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from ade_db.models import File
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_delete_document_marks_deleted(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    """Soft deletion should flag the record and allow restore."""

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

    active_list = await async_client.get(f"{workspace_base}/documents", headers=headers)
    assert active_list.status_code == 200, active_list.text
    assert all(item["id"] != document_id for item in active_list.json()["items"])

    deleted_list = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"lifecycle": "deleted"},
    )
    assert deleted_list.status_code == 200, deleted_list.text
    deleted_ids = {item["id"] for item in deleted_list.json()["items"]}
    assert document_id in deleted_ids

    row = db_session.get(File, UUID(document_id))
    assert row is not None
    assert row.deleted_at is not None

    restore_response = await async_client.post(
        f"{workspace_base}/documents/{document_id}/restore",
        headers=headers,
    )
    assert restore_response.status_code == 200, restore_response.text
    assert restore_response.json()["id"] == document_id

    restored_detail = await async_client.get(f"{workspace_base}/documents/{document_id}", headers=headers)
    assert restored_detail.status_code == 200, restored_detail.text

    deleted_after_restore = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"lifecycle": "deleted"},
    )
    assert deleted_after_restore.status_code == 200, deleted_after_restore.text
    deleted_after_restore_ids = {item["id"] for item in deleted_after_restore.json()["items"]}
    assert document_id not in deleted_after_restore_ids

    active_after_restore = await async_client.get(f"{workspace_base}/documents", headers=headers)
    assert active_after_restore.status_code == 200, active_after_restore.text
    active_after_restore_ids = {item["id"] for item in active_after_restore.json()["items"]}
    assert document_id in active_after_restore_ids


async def test_batch_delete_and_restore_documents(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    upload_one = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delete-batch-one.txt", b"one", "text/plain")},
    )
    assert upload_one.status_code == 201, upload_one.text
    upload_two = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delete-batch-two.txt", b"two", "text/plain")},
    )
    assert upload_two.status_code == 201, upload_two.text

    id_one = upload_one.json()["id"]
    id_two = upload_two.json()["id"]

    deleted = await async_client.post(
        f"{workspace_base}/documents/batch/delete",
        headers=headers,
        json={"documentIds": [id_one, id_two]},
    )
    assert deleted.status_code == 200, deleted.text
    assert set(deleted.json()["documentIds"]) == {id_one, id_two}

    deleted_list = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"lifecycle": "deleted"},
    )
    assert deleted_list.status_code == 200, deleted_list.text
    deleted_ids = {item["id"] for item in deleted_list.json()["items"]}
    assert {id_one, id_two}.issubset(deleted_ids)

    restored = await async_client.post(
        f"{workspace_base}/documents/batch/restore",
        headers=headers,
        json={"documentIds": [id_one, id_two]},
    )
    assert restored.status_code == 200, restored.text
    assert set(restored.json()["documentIds"]) == {id_one, id_two}

    active_list = await async_client.get(f"{workspace_base}/documents", headers=headers)
    assert active_list.status_code == 200, active_list.text
    active_ids = {item["id"] for item in active_list.json()["items"]}
    assert {id_one, id_two}.issubset(active_ids)
