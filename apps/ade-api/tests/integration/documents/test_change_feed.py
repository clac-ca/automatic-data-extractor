from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.models import (
    Document,
    DocumentChange,
    DocumentChangeType,
    DocumentSource,
    DocumentStatus,
)
from tests.utils import login

pytestmark = pytest.mark.asyncio


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
    document_id = upload.json()["id"]

    baseline = await async_client.get(
        f"{workspace_base}/documents/changes",
        headers=headers,
        params={"cursor": "latest"},
    )
    assert baseline.status_code == 200, baseline.text
    baseline_cursor = baseline.json()["nextCursor"]

    patch = await async_client.patch(
        f"{workspace_base}/documents/{document_id}/tags",
        headers=headers,
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
        entry["type"] == "document.upsert" and entry["row"]["id"] == document_id
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
    old_change = DocumentChange(
        workspace_id=workspace_id,
        document_id=doc.id,
        type=DocumentChangeType.UPSERT,
        payload={},
        occurred_at=now - timedelta(seconds=10),
    )
    fresh_change = DocumentChange(
        workspace_id=workspace_id,
        document_id=doc.id,
        type=DocumentChangeType.UPSERT,
        payload={},
        occurred_at=now,
    )
    session.add_all([old_change, fresh_change])
    await session.flush()
    await session.commit()

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
    assert payload["type"] == "resync_required"
    assert str(fresh_change.cursor) in (payload.get("detail") or "")
