"""Document comments API tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import anyio
import pytest
from httpx import AsyncClient

from ade_api.common.ids import generate_uuid7
from ade_api.models import Document, DocumentSource
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def _create_document(db_session, *, workspace_id, user_id) -> Document:
    now = datetime.now(tz=UTC)
    doc = Document(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        original_filename="comment-doc.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        byte_size=1024,
        sha256="f" * 64,
        stored_uri="comment-doc",
        attributes={},
        uploaded_by_user_id=user_id,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=now + timedelta(days=30),
    )
    db_session.add(doc)
    await anyio.to_thread.run_sync(db_session.commit)
    return doc


async def test_list_document_comments_empty(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    member = seed_identity.member
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=member.id,
    )

    token, _ = await login(async_client, email=member.email, password=member.password)
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"] == []
    assert payload["meta"]["hasMore"] is False
    assert payload["meta"]["nextCursor"] is None


async def test_create_comment_and_list(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    member = seed_identity.member
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=member.id,
    )

    token, _ = await login(async_client, email=member.email, password=member.password)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "body": "Hello @you",
        "mentions": [str(member.id)],
    }

    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments",
        headers=headers,
        json=payload,
    )

    assert created.status_code == 201, created.text
    created_payload = created.json()
    assert created_payload["body"] == payload["body"]
    assert created_payload["author"]["id"] == str(member.id)
    assert created_payload["mentions"][0]["id"] == str(member.id)

    listing = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments",
        headers=headers,
    )

    assert listing.status_code == 200, listing.text
    list_payload = listing.json()
    assert len(list_payload["items"]) == 1
    assert list_payload["items"][0]["body"] == payload["body"]


async def test_create_comment_rejects_non_member_mentions(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    member = seed_identity.member
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=member.id,
    )

    token, _ = await login(async_client, email=member.email, password=member.password)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "body": "Hello @orphan",
        "mentions": [str(seed_identity.orphan.id)],
    }

    response = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422, response.text
