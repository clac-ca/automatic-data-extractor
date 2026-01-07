from __future__ import annotations

from uuid import uuid4

import pytest

from ade_api.common.time import utc_now
from ade_api.features.documents.change_feed import DocumentEventsService

pytestmark = pytest.mark.asyncio


async def test_change_feed_appends_in_order(session, settings) -> None:
    service = DocumentEventsService(session=session, settings=settings)
    workspace_id = uuid4()
    now = utc_now()

    first_id = uuid4()
    second_id = uuid4()

    await service.record_changed(
        workspace_id=workspace_id,
        document_id=first_id,
        document_version=1,
        occurred_at=now,
    )
    await service.record_changed(
        workspace_id=workspace_id,
        document_id=second_id,
        document_version=1,
        occurred_at=now,
    )

    events = await service.fetch_changes_after(workspace_id=workspace_id, cursor=0, limit=10)
    assert len(events) == 2
    assert events[0].cursor < events[1].cursor
    assert events[0].event_type.value == "document.changed"

    page = await service.list_changes(
        workspace_id=workspace_id,
        cursor=int(events[0].cursor),
        limit=10,
    )
    assert len(page.items) == 1
    assert page.items[0].cursor == events[1].cursor


async def test_fetch_changes_after_respects_cursor_and_limit(session, settings) -> None:
    service = DocumentEventsService(session=session, settings=settings)
    workspace_id = uuid4()
    now = utc_now()

    first_id = uuid4()
    second_id = uuid4()
    third_id = uuid4()

    await service.record_changed(
        workspace_id=workspace_id,
        document_id=first_id,
        document_version=1,
        occurred_at=now,
    )
    await service.record_changed(
        workspace_id=workspace_id,
        document_id=second_id,
        document_version=2,
        occurred_at=now,
    )
    await service.record_changed(
        workspace_id=workspace_id,
        document_id=third_id,
        document_version=3,
        occurred_at=now,
    )

    events = await service.fetch_changes_after(workspace_id=workspace_id, cursor=0, limit=10)
    assert len(events) == 3
    after_cursor = int(events[0].cursor)

    events = await service.fetch_changes_after(
        workspace_id=workspace_id,
        cursor=after_cursor,
        limit=1,
    )
    assert len(events) == 1
    assert int(events[0].cursor) > after_cursor

    remaining = await service.fetch_changes_after(
        workspace_id=workspace_id,
        cursor=int(events[0].cursor),
        limit=10,
    )
    assert len(remaining) == 1
    assert int(remaining[0].cursor) > int(events[0].cursor)
