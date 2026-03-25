"""Document activity/thread API tests."""

from __future__ import annotations

from datetime import timedelta

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_api.common.ids import generate_uuid7
from ade_db.models import (
    File,
    FileKind,
    FileVersion,
    FileVersionOrigin,
    Run,
    RunOperation,
    RunStatus,
    WorkspaceMembership,
)
from tests.api.integration.documents.helpers import ensure_configuration
from tests.api.integration.helpers_access import create_group_with_workspace_role
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def _create_document(db_session, *, workspace_id, user_id) -> File:
    file_id = generate_uuid7()
    version_id = generate_uuid7()
    name = "comment-doc.xlsx"
    doc = File(
        id=file_id,
        workspace_id=workspace_id,
        kind=FileKind.INPUT,
        name=name,
        name_key=name.casefold(),
        blob_name=f"{workspace_id}/files/{file_id}",
        attributes={},
        uploaded_by_user_id=user_id,
        comment_count=0,
    )
    version = FileVersion(
        id=version_id,
        file_id=file_id,
        version_no=1,
        origin=FileVersionOrigin.UPLOADED,
        created_by_user_id=user_id,
        sha256="f" * 64,
        byte_size=1024,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename_at_upload=name,
        storage_version_id="v1",
    )
    doc.current_version = version
    doc.versions.append(version)
    db_session.add_all([doc, version])
    await anyio.to_thread.run_sync(db_session.commit)
    return doc


async def _seed_run(db_session, *, workspace_id, document: File, user_id) -> Run:
    configuration_id = await ensure_configuration(db_session, workspace_id)
    refreshed = await anyio.to_thread.run_sync(db_session.get, File, document.id)
    assert refreshed is not None
    assert refreshed.current_version_id is not None
    created_at = refreshed.created_at + timedelta(minutes=5)
    run = Run(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        submitted_by_user_id=user_id,
        status=RunStatus.SUCCEEDED,
        operation=RunOperation.PROCESS,
        input_file_version_id=refreshed.current_version_id,
        deps_digest="sha256:test-run",
        created_at=created_at,
        started_at=created_at + timedelta(seconds=10),
        completed_at=created_at + timedelta(minutes=1),
        exit_code=0,
    )
    refreshed.last_run_id = run.id
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)
    return run


async def _auth_headers(async_client: AsyncClient, user) -> dict[str, str]:
    token, _ = await login(async_client, email=user.email, password=user.password)
    return {"X-API-Key": token}


def _mention_payload(body: str, label: str, user_id) -> dict[str, object]:
    start = body.index(label)
    return {
        "userId": str(user_id),
        "start": start,
        "end": start + len(label),
    }


async def test_get_document_activity_starts_with_upload_event(
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

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=await _auth_headers(async_client, member),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["type"] for item in payload["items"]] == ["document"]
    assert payload["items"][0]["title"] == "Document uploaded"
    assert payload["items"][0]["thread"] is None


async def test_note_thread_appends_to_bottom_with_mentions(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    mentioned = seed_identity.member_with_manage
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )

    label = f"@{mentioned.email}"
    body = f"Please review {label}"
    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={
            "anchorType": "note",
            "body": body,
            "mentions": [_mention_payload(body, label, mentioned.id)],
        },
    )

    assert created.status_code == 201, created.text
    thread = created.json()
    assert thread["anchorType"] == "note"
    assert [comment["body"] for comment in thread["comments"]] == [body]
    assert thread["comments"][0].get("editedAt") is None

    activity = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=await _auth_headers(async_client, author),
    )

    assert activity.status_code == 200, activity.text
    items = activity.json()["items"]
    assert [item["type"] for item in items] == ["document", "note"]
    assert items[1]["thread"]["comments"][0]["mentions"] == [
        {
            "user": {
                "id": str(mentioned.id),
                "email": mentioned.email,
                "name": None,
            },
            "start": body.index(label),
            "end": body.index(label) + len(label),
        }
    ]


async def test_note_thread_accepts_mentions_for_workspace_principals_without_membership(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    mentioned = seed_identity.member_with_manage
    membership = db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == seed_identity.workspace_id,
            WorkspaceMembership.user_id == mentioned.id,
        )
    ).scalar_one_or_none()
    assert membership is not None
    db_session.delete(membership)
    await anyio.to_thread.run_sync(db_session.commit)

    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )

    label = f"@{mentioned.email}"
    body = f"Please review {label}"
    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={
            "anchorType": "note",
            "body": body,
            "mentions": [_mention_payload(body, label, mentioned.id)],
        },
    )

    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["comments"][0]["mentions"][0]["user"]["id"] == str(mentioned.id)


async def test_note_thread_accepts_mentions_for_group_derived_workspace_members(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    mentioned = seed_identity.orphan
    membership = db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == seed_identity.workspace_id,
            WorkspaceMembership.user_id == mentioned.id,
        )
    ).scalar_one_or_none()
    assert membership is None

    create_group_with_workspace_role(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=mentioned.id,
        display_name="Mention Collaborators",
        slug=f"mention-collaborators-{generate_uuid7()}",
    )
    await anyio.to_thread.run_sync(db_session.commit)

    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )

    label = f"@{mentioned.email}"
    body = f"Please review {label}"
    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={
            "anchorType": "note",
            "body": body,
            "mentions": [_mention_payload(body, label, mentioned.id)],
        },
    )

    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["comments"][0]["mentions"] == [
        {
            "user": {
                "id": str(mentioned.id),
                "email": mentioned.email,
            },
            "start": body.index(label),
            "end": body.index(label) + len(label),
        }
    ]


async def test_reply_to_document_and_run_items_keeps_timeline_position(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )
    run = await _seed_run(
        db_session,
        workspace_id=seed_identity.workspace_id,
        document=document,
        user_id=author.id,
    )
    headers = await _auth_headers(async_client, author)

    upload_thread = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={
            "anchorType": "document",
            "anchorId": str(document.id),
            "body": "Question about the upload",
            "mentions": [],
        },
    )
    assert upload_thread.status_code == 201, upload_thread.text

    run_thread = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={
            "anchorType": "run",
            "anchorId": str(run.id),
            "body": "The run looks good",
            "mentions": [],
        },
    )
    assert run_thread.status_code == 201, run_thread.text
    run_thread_id = run_thread.json()["id"]

    reply = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads/{run_thread_id}/comments",
        headers=headers,
        json={"body": "Follow-up on the run", "mentions": []},
    )
    assert reply.status_code == 201, reply.text

    activity = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=headers,
    )

    assert activity.status_code == 200, activity.text
    items = activity.json()["items"]
    assert [item["type"] for item in items] == ["document", "run"]
    assert [comment["body"] for comment in items[0]["thread"]["comments"]] == [
        "Question about the upload"
    ]
    assert [comment["body"] for comment in items[1]["thread"]["comments"]] == [
        "The run looks good",
        "Follow-up on the run",
    ]

    await anyio.to_thread.run_sync(db_session.expire_all)
    stored_document = await anyio.to_thread.run_sync(db_session.get, File, document.id)
    assert stored_document is not None
    assert stored_document.comment_count == 3


async def test_edit_comment_sets_edited_at_and_restricts_to_author(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    other_user = seed_identity.member_with_manage
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )

    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={"anchorType": "note", "body": "Original body", "mentions": []},
    )
    assert created.status_code == 201, created.text
    comment_id = created.json()["comments"][0]["id"]

    forbidden = await async_client.patch(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{comment_id}",
        headers=await _auth_headers(async_client, other_user),
        json={"body": "Other user edit", "mentions": []},
    )
    assert forbidden.status_code == 403, forbidden.text

    label = f"@{other_user.email}"
    edited_body = f"Updated for {label}"
    edited = await async_client.patch(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{comment_id}",
        headers=await _auth_headers(async_client, author),
        json={
            "body": edited_body,
            "mentions": [_mention_payload(edited_body, label, other_user.id)],
        },
    )

    assert edited.status_code == 200, edited.text
    edited_payload = edited.json()
    assert edited_payload["body"] == edited_body
    assert edited_payload["editedAt"] is not None
    assert edited_payload["threadId"] == created.json()["id"]
    assert edited_payload["mentions"][0]["user"]["id"] == str(other_user.id)


async def test_create_thread_rejects_invalid_anchor_and_mentions(
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
    headers = await _auth_headers(async_client, member)

    invalid_note_anchor = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={
            "anchorType": "note",
            "anchorId": str(document.id),
            "body": "Bad note anchor",
            "mentions": [],
        },
    )
    assert invalid_note_anchor.status_code == 422, invalid_note_anchor.text

    invalid_run_anchor = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={
            "anchorType": "run",
            "anchorId": str(generate_uuid7()),
            "body": "Bad run anchor",
            "mentions": [],
        },
    )
    assert invalid_run_anchor.status_code == 422, invalid_run_anchor.text

    non_member_label = "@orphan"
    non_member_response = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={
            "anchorType": "note",
            "body": f"Hello {non_member_label}",
            "mentions": [
                _mention_payload(
                    f"Hello {non_member_label}",
                    non_member_label,
                    seed_identity.orphan.id,
                )
            ],
        },
    )
    assert non_member_response.status_code == 422, non_member_response.text


async def test_direct_note_threads_render_oldest_first(
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
    headers = await _auth_headers(async_client, member)

    first = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={"anchorType": "note", "body": "First note", "mentions": []},
    )
    second = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={"anchorType": "note", "body": "Second note", "mentions": []},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    activity = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=headers,
    )

    assert activity.status_code == 200, activity.text
    items = activity.json()["items"]
    assert [item["type"] for item in items] == ["document", "note", "note"]
    assert [item["thread"]["comments"][0]["body"] for item in items[1:]] == [
        "First note",
        "Second note",
    ]


async def test_existing_note_thread_rows_appear_in_activity(
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
    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, member),
        json={"anchorType": "note", "body": "Stored note", "mentions": []},
    )
    assert created.status_code == 201, created.text

    activity = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=await _auth_headers(async_client, member),
    )

    assert activity.status_code == 200, activity.text
    note_item = activity.json()["items"][1]
    assert note_item["type"] == "note"
    assert note_item["thread"]["comments"][0]["body"] == "Stored note"


async def test_delete_comment_restricts_to_author_and_removes_empty_note_thread(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    other_user = seed_identity.member_with_manage
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )

    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={"anchorType": "note", "body": "Delete me", "mentions": []},
    )
    assert created.status_code == 201, created.text
    comment_id = created.json()["comments"][0]["id"]

    forbidden = await async_client.delete(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{comment_id}",
        headers=await _auth_headers(async_client, other_user),
    )
    assert forbidden.status_code == 403, forbidden.text

    deleted = await async_client.delete(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{comment_id}",
        headers=await _auth_headers(async_client, author),
    )
    assert deleted.status_code == 204, deleted.text

    activity = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=await _auth_headers(async_client, author),
    )
    assert activity.status_code == 200, activity.text
    assert [item["type"] for item in activity.json()["items"]] == ["document"]

    await anyio.to_thread.run_sync(db_session.expire_all)
    stored_document = await anyio.to_thread.run_sync(db_session.get, File, document.id)
    assert stored_document is not None
    assert stored_document.comment_count == 0


async def test_delete_root_comment_from_note_thread_promotes_next_reply(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )
    headers = await _auth_headers(async_client, author)

    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={"anchorType": "note", "body": "Original note", "mentions": []},
    )
    assert created.status_code == 201, created.text
    thread_id = created.json()["id"]
    root_comment_id = created.json()["comments"][0]["id"]

    reply = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads/{thread_id}/comments",
        headers=headers,
        json={"body": "Reply takes over", "mentions": []},
    )
    assert reply.status_code == 201, reply.text

    deleted = await async_client.delete(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{root_comment_id}",
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    activity = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=headers,
    )
    assert activity.status_code == 200, activity.text
    items = activity.json()["items"]
    assert [item["type"] for item in items] == ["document", "note"]
    assert [comment["body"] for comment in items[1]["thread"]["comments"]] == ["Reply takes over"]

    await anyio.to_thread.run_sync(db_session.expire_all)
    stored_document = await anyio.to_thread.run_sync(db_session.get, File, document.id)
    assert stored_document is not None
    assert stored_document.comment_count == 1


async def test_delete_reply_and_last_comment_from_anchored_thread_keeps_event_row(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )
    run = await _seed_run(
        db_session,
        workspace_id=seed_identity.workspace_id,
        document=document,
        user_id=author.id,
    )
    headers = await _auth_headers(async_client, author)

    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=headers,
        json={
            "anchorType": "run",
            "anchorId": str(run.id),
            "body": "Anchored root",
            "mentions": [],
        },
    )
    assert created.status_code == 201, created.text
    thread_id = created.json()["id"]
    root_comment_id = created.json()["comments"][0]["id"]

    reply = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads/{thread_id}/comments",
        headers=headers,
        json={"body": "Anchored reply", "mentions": []},
    )
    assert reply.status_code == 201, reply.text
    reply_comment_id = reply.json()["id"]

    deleted_reply = await async_client.delete(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{reply_comment_id}",
        headers=headers,
    )
    assert deleted_reply.status_code == 204, deleted_reply.text

    activity_after_reply_delete = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=headers,
    )
    assert activity_after_reply_delete.status_code == 200, activity_after_reply_delete.text
    items = activity_after_reply_delete.json()["items"]
    assert [item["type"] for item in items] == ["document", "run"]
    assert [comment["body"] for comment in items[1]["thread"]["comments"]] == ["Anchored root"]

    deleted_root = await async_client.delete(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{root_comment_id}",
        headers=headers,
    )
    assert deleted_root.status_code == 204, deleted_root.text

    final_activity = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/activity",
        headers=headers,
    )
    assert final_activity.status_code == 200, final_activity.text
    final_items = final_activity.json()["items"]
    assert [item["type"] for item in final_items] == ["document", "run"]
    assert final_items[1]["thread"] is None

    await anyio.to_thread.run_sync(db_session.expire_all)
    stored_document = await anyio.to_thread.run_sync(db_session.get, File, document.id)
    assert stored_document is not None
    assert stored_document.comment_count == 0
