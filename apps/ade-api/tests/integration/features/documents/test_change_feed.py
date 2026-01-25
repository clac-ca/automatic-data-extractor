from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from ade_api.common.time import utc_now
from ade_api.features.documents.change_feed import DocumentEventsService
from ade_api.models import Document, DocumentSource, Workspace


def _seed_workspace(session, workspace_id):
    workspace = Workspace(
        id=workspace_id,
        name="Test Workspace",
        slug=f"ws-{workspace_id.hex[:8]}",
    )
    session.add(workspace)
    session.flush()


def _seed_document(session, workspace_id, document_id, now):
    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        original_filename="example.txt",
        content_type="text/plain",
        byte_size=1,
        sha256="0" * 64,
        stored_uri=f"{document_id}.bin",
        attributes={},
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=now + timedelta(days=1),
    )
    session.add(document)
    session.flush()


def test_change_feed_appends_in_order(session, settings) -> None:
    service = DocumentEventsService(session=session, settings=settings)
    workspace_id = uuid4()
    now = utc_now()

    first_id = uuid4()
    second_id = uuid4()

    _seed_workspace(session, workspace_id)
    _seed_document(session, workspace_id, first_id, now)
    _seed_document(session, workspace_id, second_id, now)

    events = service.fetch_changes_after(workspace_id=workspace_id, cursor=0, limit=10)
    assert len(events) == 2
    assert events[0].cursor < events[1].cursor
    assert events[0].event_type.value == "document.changed"

    page = service.list_changes(
        workspace_id=workspace_id,
        cursor=int(events[0].cursor),
        limit=10,
    )
    assert len(page.items) == 1
    assert page.items[0].cursor == events[1].cursor


def test_fetch_changes_after_respects_cursor_and_limit(session, settings) -> None:
    service = DocumentEventsService(session=session, settings=settings)
    workspace_id = uuid4()
    now = utc_now()

    first_id = uuid4()
    second_id = uuid4()
    third_id = uuid4()

    _seed_workspace(session, workspace_id)
    _seed_document(session, workspace_id, first_id, now)
    _seed_document(session, workspace_id, second_id, now)
    _seed_document(session, workspace_id, third_id, now)

    events = service.fetch_changes_after(workspace_id=workspace_id, cursor=0, limit=10)
    assert len(events) == 3
    after_cursor = int(events[0].cursor)

    events = service.fetch_changes_after(
        workspace_id=workspace_id,
        cursor=after_cursor,
        limit=1,
    )
    assert len(events) == 1
    assert int(events[0].cursor) > after_cursor

    remaining = service.fetch_changes_after(
        workspace_id=workspace_id,
        cursor=int(events[0].cursor),
        limit=10,
    )
    assert len(remaining) == 1
    assert int(remaining[0].cursor) > int(events[0].cursor)
