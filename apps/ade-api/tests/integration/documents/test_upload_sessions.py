from __future__ import annotations

import pytest

from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_upload_session_resume_and_commit(async_client, seed_identity) -> None:
    manager = seed_identity.member_with_manage
    token, _ = await login(
        async_client,
        email=manager.email,
        password=manager.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    content = b"abcdef"
    create = await async_client.post(
        f"{workspace_base}/documents/uploadSessions",
        headers=headers,
        json={
            "filename": "resume.txt",
            "byte_size": len(content),
            "content_type": "text/plain",
        },
    )
    assert create.status_code == 201, create.text
    session_id = create.json()["upload_session_id"]

    first_chunk = await async_client.put(
        f"{workspace_base}/documents/uploadSessions/{session_id}",
        headers={
            **headers,
            "Content-Range": "bytes 0-2/6",
        },
        content=content[:3],
    )
    assert first_chunk.status_code == 202, first_chunk.text
    assert first_chunk.json()["next_expected_ranges"] == ["3-"]
    assert first_chunk.json()["upload_complete"] is False

    status = await async_client.get(
        f"{workspace_base}/documents/uploadSessions/{session_id}",
        headers=headers,
    )
    assert status.status_code == 200, status.text
    assert status.json()["received_bytes"] == 3
    assert status.json()["next_expected_ranges"] == ["3-"]

    second_chunk = await async_client.put(
        f"{workspace_base}/documents/uploadSessions/{session_id}",
        headers={
            **headers,
            "Content-Range": "bytes 3-5/6",
        },
        content=content[3:],
    )
    assert second_chunk.status_code == 202, second_chunk.text
    assert second_chunk.json()["upload_complete"] is True

    commit = await async_client.post(
        f"{workspace_base}/documents/uploadSessions/{session_id}/commit",
        headers=headers,
    )
    assert commit.status_code == 201, commit.text
    payload = commit.json()
    assert payload["name"] == "resume.txt"
    assert payload["byte_size"] == len(content)


async def test_upload_session_cancel(async_client, seed_identity) -> None:
    manager = seed_identity.member_with_manage
    token, _ = await login(
        async_client,
        email=manager.email,
        password=manager.password,
    )
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"Authorization": f"Bearer {token}"}

    create = await async_client.post(
        f"{workspace_base}/documents/uploadSessions",
        headers=headers,
        json={
            "filename": "cancel.txt",
            "byte_size": 4,
            "content_type": "text/plain",
        },
    )
    assert create.status_code == 201, create.text
    session_id = create.json()["upload_session_id"]

    cancel = await async_client.delete(
        f"{workspace_base}/documents/uploadSessions/{session_id}",
        headers=headers,
    )
    assert cancel.status_code == 204

    status = await async_client.get(
        f"{workspace_base}/documents/uploadSessions/{session_id}",
        headers=headers,
    )
    assert status.status_code == 404
