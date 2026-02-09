"""Document deletion tests."""

from __future__ import annotations

from uuid import UUID, uuid4

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
    restored_payload = restored.json()
    assert set(restored_payload["restoredIds"]) == {id_one, id_two}
    assert restored_payload["conflicts"] == []
    assert restored_payload["notFoundIds"] == []

    active_list = await async_client.get(f"{workspace_base}/documents", headers=headers)
    assert active_list.status_code == 200, active_list.text
    active_ids = {item["id"] for item in active_list.json()["items"]}
    assert {id_one, id_two}.issubset(active_ids)


async def test_delete_reupload_same_name_releases_name_key(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    first_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("repeat-name.txt", b"first", "text/plain")},
    )
    assert first_upload.status_code == 201, first_upload.text
    first_document_id = first_upload.json()["id"]

    deleted = await async_client.delete(
        f"{workspace_base}/documents/{first_document_id}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    deleted_row = db_session.get(File, UUID(first_document_id))
    assert deleted_row is not None
    assert deleted_row.name == "repeat-name.txt"
    assert deleted_row.name_key == "repeat-name.txt"

    second_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("repeat-name.txt", b"second", "text/plain")},
    )
    assert second_upload.status_code == 201, second_upload.text
    second_document_id = second_upload.json()["id"]
    assert second_document_id != first_document_id

    active_list = await async_client.get(f"{workspace_base}/documents", headers=headers)
    assert active_list.status_code == 200, active_list.text
    active_ids = {item["id"] for item in active_list.json()["items"]}
    assert second_document_id in active_ids
    assert first_document_id not in active_ids

    deleted_list = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"lifecycle": "deleted"},
    )
    assert deleted_list.status_code == 200, deleted_list.text
    deleted_ids = {item["id"] for item in deleted_list.json()["items"]}
    assert first_document_id in deleted_ids


async def test_restore_conflict_returns_409_and_supports_renamed_restore(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    first_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("restore-clash.txt", b"first", "text/plain")},
    )
    assert first_upload.status_code == 201, first_upload.text
    deleted_document_id = first_upload.json()["id"]

    deleted = await async_client.delete(
        f"{workspace_base}/documents/{deleted_document_id}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    second_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("restore-clash.txt", b"second", "text/plain")},
    )
    assert second_upload.status_code == 201, second_upload.text
    active_document_id = second_upload.json()["id"]

    restore_conflict = await async_client.post(
        f"{workspace_base}/documents/{deleted_document_id}/restore",
        headers=headers,
    )
    assert restore_conflict.status_code == 409, restore_conflict.text
    problem = restore_conflict.json()
    assert isinstance(problem["detail"], str) and problem["detail"].strip()
    errors = {
        item["path"]: item["message"]
        for item in problem.get("errors", [])
        if isinstance(item, dict) and "path" in item and "message" in item
    }
    assert errors["documentId"] == deleted_document_id
    assert errors["conflictingDocumentId"] == active_document_id
    assert errors["name"] == "restore-clash.txt"
    assert errors["conflictingName"] == "restore-clash.txt"
    suggested_name = errors["suggestedName"]
    assert isinstance(suggested_name, str) and suggested_name.strip()

    restored = await async_client.post(
        f"{workspace_base}/documents/{deleted_document_id}/restore",
        headers=headers,
        json={"name": suggested_name},
    )
    assert restored.status_code == 200, restored.text
    restored_payload = restored.json()
    assert restored_payload["id"] == deleted_document_id
    assert restored_payload["name"] == suggested_name


async def test_batch_restore_partial_with_conflicts_and_not_found(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    conflict_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("batch-clash.txt", b"first", "text/plain")},
    )
    assert conflict_upload.status_code == 201, conflict_upload.text
    conflict_deleted_id = conflict_upload.json()["id"]

    conflict_deleted = await async_client.delete(
        f"{workspace_base}/documents/{conflict_deleted_id}",
        headers=headers,
    )
    assert conflict_deleted.status_code == 204, conflict_deleted.text

    conflict_active = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("batch-clash.txt", b"second", "text/plain")},
    )
    assert conflict_active.status_code == 201, conflict_active.text
    conflict_active_id = conflict_active.json()["id"]

    restorable_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("batch-restore-ok.txt", b"ok", "text/plain")},
    )
    assert restorable_upload.status_code == 201, restorable_upload.text
    restorable_id = restorable_upload.json()["id"]

    restorable_deleted = await async_client.delete(
        f"{workspace_base}/documents/{restorable_id}",
        headers=headers,
    )
    assert restorable_deleted.status_code == 204, restorable_deleted.text

    missing_id = str(uuid4())
    restore = await async_client.post(
        f"{workspace_base}/documents/batch/restore",
        headers=headers,
        json={"documentIds": [conflict_deleted_id, restorable_id, missing_id]},
    )
    assert restore.status_code == 200, restore.text
    payload = restore.json()

    assert payload["restoredIds"] == [restorable_id]
    assert payload["notFoundIds"] == [missing_id]
    assert len(payload["conflicts"]) == 1
    conflict_entry = payload["conflicts"][0]
    assert conflict_entry["documentId"] == conflict_deleted_id
    assert conflict_entry["name"] == "batch-clash.txt"
    assert conflict_entry["conflictingDocumentId"] == conflict_active_id
    assert conflict_entry["conflictingName"] == "batch-clash.txt"
    assert isinstance(conflict_entry["suggestedName"], str) and conflict_entry["suggestedName"].strip()


async def test_restore_with_extension_change_returns_422(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("extension-lock.txt", b"payload", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    deleted = await async_client.delete(
        f"{workspace_base}/documents/{document_id}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    restore = await async_client.post(
        f"{workspace_base}/documents/{document_id}/restore",
        headers=headers,
        json={"name": "extension-lock.csv"},
    )
    assert restore.status_code == 422, restore.text
    assert "extension" in str(restore.json().get("detail", "")).lower()


async def test_restore_with_conflicting_requested_name_returns_409(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    deleted_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("restore-target.txt", b"deleted", "text/plain")},
    )
    assert deleted_upload.status_code == 201, deleted_upload.text
    deleted_document_id = deleted_upload.json()["id"]

    deleted = await async_client.delete(
        f"{workspace_base}/documents/{deleted_document_id}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    active_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("occupied-name.txt", b"active", "text/plain")},
    )
    assert active_upload.status_code == 201, active_upload.text
    active_document_id = active_upload.json()["id"]

    restore_conflict = await async_client.post(
        f"{workspace_base}/documents/{deleted_document_id}/restore",
        headers=headers,
        json={"name": "occupied-name.txt"},
    )
    assert restore_conflict.status_code == 409, restore_conflict.text
    problem = restore_conflict.json()
    errors = {
        item["path"]: item["message"]
        for item in problem.get("errors", [])
        if isinstance(item, dict) and "path" in item and "message" in item
    }
    assert errors["documentId"] == deleted_document_id
    assert errors["conflictingDocumentId"] == active_document_id
    assert errors["name"] == "occupied-name.txt"
    assert errors["conflictingName"] == "occupied-name.txt"


async def test_batch_restore_handles_multiple_deleted_docs_with_same_name(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    first_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("same-name.txt", b"first", "text/plain")},
    )
    assert first_upload.status_code == 201, first_upload.text
    first_id = first_upload.json()["id"]

    first_deleted = await async_client.delete(
        f"{workspace_base}/documents/{first_id}",
        headers=headers,
    )
    assert first_deleted.status_code == 204, first_deleted.text

    second_upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("same-name.txt", b"second", "text/plain")},
    )
    assert second_upload.status_code == 201, second_upload.text
    second_id = second_upload.json()["id"]

    second_deleted = await async_client.delete(
        f"{workspace_base}/documents/{second_id}",
        headers=headers,
    )
    assert second_deleted.status_code == 204, second_deleted.text

    restore = await async_client.post(
        f"{workspace_base}/documents/batch/restore",
        headers=headers,
        json={"documentIds": [first_id, second_id]},
    )
    assert restore.status_code == 200, restore.text
    payload = restore.json()

    assert payload["restoredIds"] == [first_id]
    assert payload["notFoundIds"] == []
    assert len(payload["conflicts"]) == 1
    conflict_entry = payload["conflicts"][0]
    assert conflict_entry["documentId"] == second_id
    assert conflict_entry["name"] == "same-name.txt"
    assert conflict_entry["conflictingDocumentId"] == first_id
    assert conflict_entry["conflictingName"] == "same-name.txt"
    assert isinstance(conflict_entry["suggestedName"], str) and conflict_entry["suggestedName"].strip()
