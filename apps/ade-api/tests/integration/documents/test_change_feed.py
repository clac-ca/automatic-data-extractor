from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import anyio
import pytest

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.models import (
    Document,
    DocumentEvent,
    DocumentEventType,
    DocumentSource,
    DocumentStatus,
)
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_document_changes_include_create_event(async_client, seed_identity) -> None:
    manager = seed_identity.member_with_manage
    token, _ = await login(
        async_client,
        email=manager.email,
        password=manager.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    listing = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"page": 1, "perPage": 1},
    )
    assert listing.status_code == 200, listing.text
    baseline_cursor = listing.json()["changesCursor"]

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("first.txt", b"hello", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    upload_payload = upload.json()
    document_id = upload_payload["id"]
    etag = upload_payload.get("etag")
    assert etag is not None
    assert etag is not None

    replay = await async_client.get(
        f"{workspace_base}/documents/changes",
        headers=headers,
        params={"cursor": baseline_cursor},
    )
    assert replay.status_code == 200, replay.text
    payload = replay.json()
    assert any(
        entry["type"] == "document.changed" and entry["documentId"] == document_id
        for entry in payload["items"]
    )


async def test_document_changes_cursor_replay(async_client, seed_identity) -> None:
    manager = seed_identity.member_with_manage
    token, _ = await login(
        async_client,
        email=manager.email,
        password=manager.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("first.txt", b"hello", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    upload_payload = upload.json()
    document_id = upload_payload["id"]
    etag = upload_payload.get("etag")

    listing = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"page": 1, "perPage": 1},
    )
    assert listing.status_code == 200, listing.text
    baseline_cursor = listing.json()["changesCursor"]

    patch = await async_client.patch(
        f"{workspace_base}/documents/{document_id}/tags",
        headers={**headers, "If-Match": etag},
        json={"add": ["finance"]},
    )
    assert patch.status_code == 200, patch.text

    replay = await async_client.get(
        f"{workspace_base}/documents/changes",
        headers=headers,
        params={"cursor": baseline_cursor},
    )
    assert replay.status_code == 200, replay.text
    payload = replay.json()
    assert payload["items"], "Expected at least one change after the cursor."
    assert any(
        entry["type"] == "document.changed" and entry["documentId"] == document_id
        for entry in payload["items"]
    )


async def test_document_changes_include_delete_event(async_client, seed_identity) -> None:
    manager = seed_identity.member_with_manage
    token, _ = await login(
        async_client,
        email=manager.email,
        password=manager.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"idem-{uuid4().hex}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("delete.txt", b"hello", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    uploaded = upload.json()
    document_id = uploaded["id"]

    listing = await async_client.get(
        f"{workspace_base}/documents",
        headers=headers,
        params={"page": 1, "perPage": 1},
    )
    assert listing.status_code == 200, listing.text
    baseline_cursor = listing.json()["changesCursor"]

    delete = await async_client.delete(
        f"{workspace_base}/documents/{document_id}",
        headers={
            **headers,
            "If-Match": uploaded["etag"],
        },
    )
    assert delete.status_code == 204, delete.text

    replay = await async_client.get(
        f"{workspace_base}/documents/changes",
        headers=headers,
        params={"cursor": baseline_cursor},
    )
    assert replay.status_code == 200, replay.text
    payload = replay.json()
    assert any(
        entry["type"] == "document.deleted" and entry["documentId"] == document_id
        for entry in payload["items"]
    )


async def test_document_changes_cursor_too_old(async_client, seed_identity, session, settings) -> None:
    settings.documents_change_feed_retention_period = timedelta(seconds=1)

    workspace_id = seed_identity.workspace_id
    user = seed_identity.member_with_manage
    doc = Document(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        original_filename="stale.txt",
        content_type="text/plain",
        byte_size=3,
        sha256="abc123",
        stored_uri="documents/stale.txt",
        attributes={},
        uploaded_by_user_id=user.id,
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now() + timedelta(days=1),
        last_run_at=None,
    )
    session.add(doc)

    now = utc_now()
    old_change = DocumentEvent(
        workspace_id=workspace_id,
        document_id=doc.id,
        event_type=DocumentEventType.CHANGED,
        document_version=1,
        occurred_at=now - timedelta(seconds=10),
    )
    fresh_change = DocumentEvent(
        workspace_id=workspace_id,
        document_id=doc.id,
        event_type=DocumentEventType.CHANGED,
        document_version=2,
        occurred_at=now,
    )
    session.add_all([old_change, fresh_change])
    await anyio.to_thread.run_sync(session.flush)
    await anyio.to_thread.run_sync(session.commit)

    token, _ = await login(
        async_client,
        email=user.email,
        password=user.password,
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/documents/changes",
        headers=headers,
        params={"cursor": "0"},
    )
    assert response.status_code == 410, response.text
    payload = response.json()
    assert payload.get("type") == "resync_required"
