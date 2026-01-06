from __future__ import annotations

from uuid import uuid4

import pytest

from ade_api.common.etag import build_etag_token, format_weak_etag
from ade_api.common.time import utc_now
from ade_api.features.documents.change_feed import DocumentChangesService
from ade_api.features.documents.schemas import DocumentFileType, DocumentListRow
from ade_api.models import DocumentStatus

pytestmark = pytest.mark.asyncio


async def test_change_feed_appends_in_order_and_payload(session, settings) -> None:
    service = DocumentChangesService(session=session, settings=settings)
    workspace_id = uuid4()
    now = utc_now()

    first_id = uuid4()
    second_id = uuid4()
    row_one = DocumentListRow(
        id=str(first_id),
        workspace_id=str(workspace_id),
        name="first.csv",
        file_type=DocumentFileType.CSV,
        status=DocumentStatus.UPLOADED,
        uploader=None,
        assignee=None,
        tags=[],
        byte_size=123,
        created_at=now,
        updated_at=now,
        activity_at=now,
        version=1,
        etag=format_weak_etag(build_etag_token(first_id, 1)),
        latest_run=None,
        latest_successful_run=None,
        latest_result=None,
    )
    row_two = DocumentListRow(
        id=str(second_id),
        workspace_id=str(workspace_id),
        name="second.csv",
        file_type=DocumentFileType.CSV,
        status=DocumentStatus.UPLOADED,
        uploader=None,
        assignee=None,
        tags=[],
        byte_size=456,
        created_at=now,
        updated_at=now,
        activity_at=now,
        version=1,
        etag=format_weak_etag(build_etag_token(second_id, 1)),
        latest_run=None,
        latest_successful_run=None,
        latest_result=None,
    )

    await service.record_upsert(
        workspace_id=workspace_id,
        document_id=first_id,
        payload=row_one.model_dump(),
        document_version=1,
        occurred_at=now,
    )
    await service.record_upsert(
        workspace_id=workspace_id,
        document_id=second_id,
        payload=row_two.model_dump(),
        document_version=1,
        occurred_at=now,
    )

    page = await service.list_changes(workspace_id=workspace_id, cursor=0, limit=10)
    assert len(page.items) == 2
    assert page.items[0].cursor < page.items[1].cursor
    DocumentListRow.model_validate(page.items[0].payload)
