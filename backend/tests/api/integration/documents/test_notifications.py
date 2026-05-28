"""Integration tests for User Notifications (Comment Mentions)."""

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
    UserNotification,
)
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


async def test_mention_creates_user_notification(
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
    body = f"Hey {label}, check this out!"

    # 1. Create a thread mentioning another user
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
    comment_id = thread["comments"][0]["id"]

    # Verify notification created in DB
    stmt = select(UserNotification).where(UserNotification.comment_id == comment_id)
    notifications = list(db_session.execute(stmt).scalars())
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.user_id == mentioned.id
    assert notification.workspace_id == seed_identity.workspace_id
    assert not notification.is_read

    # 2. Verify mentioned user can list the notification
    notif_resp = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/notifications",
        headers=await _auth_headers(async_client, mentioned),
    )
    assert notif_resp.status_code == 200, notif_resp.text
    notif_list = notif_resp.json()
    assert len(notif_list) >= 1
    # Make sure we find our specific notification
    matching_notif = next((n for n in notif_list if n["id"] == str(notification.id)), None)
    assert matching_notif is not None
    assert matching_notif["isRead"] is False
    assert matching_notif["documentName"] == "comment-doc.xlsx"
    assert matching_notif["documentDeletedAt"] is None
    assert matching_notif["comment"]["body"] == body

    archive_resp = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/archive",
        headers=await _auth_headers(async_client, author),
    )
    assert archive_resp.status_code == 204, archive_resp.text

    archived_notif_resp = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/notifications",
        headers=await _auth_headers(async_client, mentioned),
    )
    assert archived_notif_resp.status_code == 200, archived_notif_resp.text
    archived_matching_notif = next(
        (n for n in archived_notif_resp.json() if n["id"] == str(notification.id)),
        None,
    )
    assert archived_matching_notif is not None
    assert archived_matching_notif["documentDeletedAt"] is not None

    # 3. Verify author (sender) does not have a notification
    author_notif_resp = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/notifications",
        headers=await _auth_headers(async_client, author),
    )
    assert author_notif_resp.status_code == 200, author_notif_resp.text
    author_list = author_notif_resp.json()
    assert not any(n["id"] == str(notification.id) for n in author_list)


async def test_self_mention_does_not_create_notification(
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

    label = f"@{author.email}"
    body = f"Note to self: {label}"

    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={
            "anchorType": "note",
            "body": body,
            "mentions": [_mention_payload(body, label, author.id)],
        },
    )

    assert created.status_code == 201, created.text
    thread = created.json()
    comment_id = thread["comments"][0]["id"]

    # Verify no notification created
    stmt = select(UserNotification).where(UserNotification.comment_id == comment_id)
    notifications = list(db_session.execute(stmt).scalars())
    assert len(notifications) == 0


async def test_updating_comment_adds_new_notifications_only(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    author = seed_identity.member
    mentioned_1 = seed_identity.member_with_manage
    mentioned_2 = seed_identity.workspace_owner
    document = await _create_document(
        db_session,
        workspace_id=seed_identity.workspace_id,
        user_id=author.id,
    )

    label_1 = f"@{mentioned_1.email}"
    body = f"Hello {label_1}"

    # Create thread with 1 mention
    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={
            "anchorType": "note",
            "body": body,
            "mentions": [_mention_payload(body, label_1, mentioned_1.id)],
        },
    )
    assert created.status_code == 201
    thread = created.json()
    comment_id = thread["comments"][0]["id"]

    # Check notification count in DB
    stmt = select(UserNotification).where(UserNotification.comment_id == comment_id)
    notifications_before = list(db_session.execute(stmt).scalars())
    assert len(notifications_before) == 1
    assert notifications_before[0].user_id == mentioned_1.id

    # Update comment to include mentioned_2 as well
    label_2 = f"@{mentioned_2.email}"
    new_body = f"Hello {label_1} and {label_2}"
    updated = await async_client.patch(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{comment_id}",
        headers=await _auth_headers(async_client, author),
        json={
            "body": new_body,
            "mentions": [
                _mention_payload(new_body, label_1, mentioned_1.id),
                _mention_payload(new_body, label_2, mentioned_2.id),
            ],
        },
    )
    assert updated.status_code == 200, updated.text

    # Verify that mentioned_2 now has a notification, but mentioned_1 does not get a duplicate
    stmt2 = select(UserNotification).where(UserNotification.comment_id == comment_id)
    notifications_after = list(db_session.execute(stmt2).scalars())
    assert len(notifications_after) == 2
    user_ids = {n.user_id for n in notifications_after}
    assert user_ids == {mentioned_1.id, mentioned_2.id}


async def test_mark_notification_as_read_and_read_all(
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

    # 1. Create a thread
    label = f"@{mentioned.email}"
    body = f"Ping {label}"
    await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={
            "anchorType": "note",
            "body": body,
            "mentions": [_mention_payload(body, label, mentioned.id)],
        },
    )

    # Get notification ID
    notif_resp = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/notifications",
        headers=await _auth_headers(async_client, mentioned),
    )
    assert notif_resp.status_code == 200
    notifs = notif_resp.json()
    assert len(notifs) >= 1
    notif_id = notifs[0]["id"]

    # 2. Mark specific notification as read
    read_resp = await async_client.patch(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/notifications/{notif_id}/read",
        headers=await _auth_headers(async_client, mentioned),
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["isRead"] is True

    # 3. Create another notification to test readAll
    await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={
            "anchorType": "note",
            "body": f"Ping again {label}",
            "mentions": [_mention_payload(f"Ping again {label}", label, mentioned.id)],
        },
    )

    # Verify there is at least 1 unread notification now
    notif_resp = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/notifications",
        headers=await _auth_headers(async_client, mentioned),
    )
    notifs = notif_resp.json()
    assert any(n["isRead"] is False for n in notifs)

    # Mark all read
    read_all_resp = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/notifications/readAll",
        headers=await _auth_headers(async_client, mentioned),
    )
    assert read_all_resp.status_code == 204

    # Verify all are read now
    notif_resp = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/notifications",
        headers=await _auth_headers(async_client, mentioned),
    )
    notifs = notif_resp.json()
    assert all(n["isRead"] is True for n in notifs)


async def test_delete_comment_cascade_deletes_notification(
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
    body = f"Notify delete {label}"

    created = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/threads",
        headers=await _auth_headers(async_client, author),
        json={
            "anchorType": "note",
            "body": body,
            "mentions": [_mention_payload(body, label, mentioned.id)],
        },
    )
    assert created.status_code == 201
    thread = created.json()
    comment_id = thread["comments"][0]["id"]

    # Verify it exists in DB
    stmt = select(UserNotification).where(UserNotification.comment_id == comment_id)
    assert len(list(db_session.execute(stmt).scalars())) == 1

    # Delete the comment via endpoint
    delete_resp = await async_client.delete(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/documents/{document.id}/comments/{comment_id}",
        headers=await _auth_headers(async_client, author),
    )
    assert delete_resp.status_code == 204

    # Verify cascade delete of notification in DB
    await anyio.to_thread.run_sync(db_session.commit)
    stmt2 = select(UserNotification).where(UserNotification.comment_id == comment_id)
    assert len(list(db_session.execute(stmt2).scalars())) == 0
