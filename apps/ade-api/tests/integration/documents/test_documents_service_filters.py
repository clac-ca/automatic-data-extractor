"""Document service filtering and sorting tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ade_api.common.list_filters import FilterItem, FilterJoinOperator, FilterOperator
from ade_api.common.sorting import resolve_sort
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_api.models import DocumentStatus, RunStatus
from tests.integration.documents.helpers import (
    build_documents_fixture,
    seed_failed_run,
)

pytestmark = pytest.mark.asyncio


async def test_list_documents_applies_filters_and_sorting(db_session, settings) -> None:
    workspace, _, _, processed, uploaded = await build_documents_fixture(db_session)

    service = DocumentsService(session=db_session, settings=settings)

    filters = [
        FilterItem(
            id="status",
            operator=FilterOperator.IN,
            value=[DocumentStatus.PROCESSED],
        ),
        FilterItem(
            id="tags",
            operator=FilterOperator.EQ,
            value="finance",
        ),
    ]
    order_by_recent = resolve_sort(
        ["-createdAt"],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        page=1,
        per_page=50,
        order_by=order_by_recent,
        filters=filters,
        join_operator=FilterJoinOperator.AND,
        q="Uploader",
    )

    assert result.total == 1
    assert [item.id for item in result.items] == [processed.id]

    # Sorting by name ascending should place the draft before the report.
    name_order = resolve_sort(
        ["name"],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    name_sorted = service.list_documents(
        workspace_id=workspace.id,
        page=1,
        per_page=50,
        order_by=name_order,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )
    assert [item.id for item in name_sorted.items] == [processed.id, uploaded.id]


async def test_activity_at_filters_within_range(db_session, settings) -> None:
    workspace, _, _, processed, uploaded = await build_documents_fixture(db_session)

    service = DocumentsService(session=db_session, settings=settings)

    now = datetime.now(tz=UTC)
    filters = [
        FilterItem(
            id="activityAt",
            operator=FilterOperator.BETWEEN,
            value=[now - timedelta(hours=1), now + timedelta(hours=1)],
        )
    ]
    order_by_default = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        page=1,
        per_page=50,
        order_by=order_by_default,
        filters=filters,
        join_operator=FilterJoinOperator.AND,
        q=None,
    )

    returned_ids = {item.id for item in result.items}
    assert uploaded.id in returned_ids
    assert processed.id in returned_ids


async def test_sorting_last_run_places_nulls_last(db_session, settings) -> None:
    workspace, _, _, processed, uploaded = await build_documents_fixture(db_session)

    service = DocumentsService(session=db_session, settings=settings)

    order_by_last_run = resolve_sort(
        ["-latestRunAt"],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        page=1,
        per_page=50,
        order_by=order_by_last_run,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )

    assert [item.id for item in result.items] == [processed.id, uploaded.id]


async def test_list_documents_includes_last_run_message(db_session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await build_documents_fixture(db_session)
    run = await seed_failed_run(
        db_session,
        workspace_id=workspace.id,
        document_id=processed.id,
        uploader_id=uploader.id,
    )

    service = DocumentsService(session=db_session, settings=settings)
    order_by = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        page=1,
        per_page=25,
        order_by=order_by,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )

    processed_record = next(item for item in result.items if item.id == processed.id)
    assert processed_record.latest_run is not None
    assert processed_record.latest_run.id == run.id
    assert processed_record.latest_run.status == RunStatus.FAILED
    assert processed_record.latest_run.error_summary == "Request failed with status 404"
    assert processed_record.latest_run.completed_at == run.completed_at

    uploaded_record = next(item for item in result.items if item.id == uploaded.id)
    assert uploaded_record.latest_run is None
