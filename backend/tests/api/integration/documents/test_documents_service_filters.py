"""Document service filtering and sorting tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ade_api.common.list_filters import FilterItem, FilterJoinOperator, FilterOperator
from ade_api.common.cursor_listing import resolve_cursor_sort
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import CURSOR_FIELDS, DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_storage import build_storage_adapter
from ade_db.models import RunStatus
from tests.api.integration.documents.helpers import (
    build_documents_fixture,
    seed_failed_run,
)

pytestmark = pytest.mark.asyncio


async def test_list_documents_applies_filters_and_sorting(db_session, settings) -> None:
    workspace, _, _, processed, uploaded = await build_documents_fixture(db_session)

    storage = build_storage_adapter(settings)
    service = DocumentsService(session=db_session, settings=settings, storage=storage)

    filters = [
        FilterItem(
            id="lastRunPhase",
            operator=FilterOperator.IN,
            value=["succeeded"],
        ),
        FilterItem(
            id="tags",
            operator=FilterOperator.EQ,
            value="finance",
        ),
    ]
    resolved_sort_recent = resolve_cursor_sort(
        ["-createdAt"],
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=resolved_sort_recent,
        include_total=True,
        include_facets=False,
        filters=filters,
        join_operator=FilterJoinOperator.AND,
        q="Uploader",
    )

    assert result.meta.total_count == 1
    assert [item.id for item in result.items] == [processed.id]

    # Sorting by name ascending should place the draft before the report.
    name_order = resolve_cursor_sort(
        ["name"],
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    name_sorted = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=name_order,
        include_total=False,
        include_facets=False,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )
    assert [item.id for item in name_sorted.items] == [processed.id, uploaded.id]


async def test_list_documents_facets_include_last_run_phase_and_file_type(db_session, settings) -> None:
    workspace, _, _, processed, uploaded = await build_documents_fixture(db_session)

    storage = build_storage_adapter(settings)
    service = DocumentsService(session=db_session, settings=settings, storage=storage)
    order_by_default = resolve_cursor_sort(
        [],
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=order_by_default,
        include_total=False,
        include_facets=True,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )

    assert result.facets is not None
    phase_buckets = {
        bucket["value"]: bucket["count"]
        for bucket in result.facets["lastRunPhase"]["buckets"]
    }
    file_type_buckets = {
        bucket["value"]: bucket["count"]
        for bucket in result.facets["fileType"]["buckets"]
    }

    assert phase_buckets["succeeded"] == 1
    assert phase_buckets[None] == 1
    assert file_type_buckets["pdf"] == 1
    assert file_type_buckets["unknown"] == 1


async def test_activity_at_filters_within_range(db_session, settings) -> None:
    workspace, _, _, processed, uploaded = await build_documents_fixture(db_session)

    storage = build_storage_adapter(settings)
    service = DocumentsService(session=db_session, settings=settings, storage=storage)

    now = datetime.now(tz=UTC)
    filters = [
        FilterItem(
            id="activityAt",
            operator=FilterOperator.BETWEEN,
            value=[now - timedelta(hours=1), now + timedelta(hours=1)],
        )
    ]
    order_by_default = resolve_cursor_sort(
        [],
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=order_by_default,
        include_total=False,
        include_facets=False,
        filters=filters,
        join_operator=FilterJoinOperator.AND,
        q=None,
    )

    returned_ids = {item.id for item in result.items}
    assert uploaded.id in returned_ids
    assert processed.id in returned_ids


async def test_sorting_last_run_places_nulls_last(db_session, settings) -> None:
    workspace, _, _, processed, uploaded = await build_documents_fixture(db_session)

    storage = build_storage_adapter(settings)
    service = DocumentsService(session=db_session, settings=settings, storage=storage)

    order_by_last_run = resolve_cursor_sort(
        ["-lastRunAt"],
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=order_by_last_run,
        include_total=False,
        include_facets=False,
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

    storage = build_storage_adapter(settings)
    service = DocumentsService(session=db_session, settings=settings, storage=storage)
    order_by = resolve_cursor_sort(
        [],
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = service.list_documents(
        workspace_id=workspace.id,
        limit=25,
        cursor=None,
        resolved_sort=order_by,
        include_total=False,
        include_facets=False,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )

    processed_record = next(item for item in result.items if item.id == processed.id)
    assert processed_record.last_run is not None
    assert processed_record.last_run.id == run.id
    assert processed_record.last_run.status == RunStatus.FAILED
    assert processed_record.last_run.error_message == "Request failed with status 404"
    assert processed_record.last_run.completed_at == run.completed_at

    uploaded_record = next(item for item in result.items if item.id == uploaded.id)
    assert uploaded_record.last_run is None
