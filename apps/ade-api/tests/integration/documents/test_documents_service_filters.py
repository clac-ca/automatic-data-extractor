"""Document service filtering and sorting tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ade_api.common.sorting import resolve_sort
from ade_api.features.documents.filters import DocumentFilters
from ade_api.features.documents.schemas import DocumentDisplayStatus
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_api.models import RunStatus
from tests.integration.documents.helpers import (
    build_documents_fixture,
    seed_failed_run,
)

pytestmark = pytest.mark.asyncio


async def test_list_documents_applies_filters_and_sorting(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await build_documents_fixture(session)

    service = DocumentsService(session=session, settings=settings)

    filters = DocumentFilters(
        status_in={DocumentDisplayStatus.READY},
        tags={"finance"},
        uploader="me",
        q="Uploader",
    )
    order_by_recent = resolve_sort(
        ["-created_at"],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=True,
        order_by=order_by_recent,
        filters=filters,
        actor=uploader,
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
    name_sorted = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=name_order,
        filters=DocumentFilters(),
        actor=uploader,
    )
    assert [item.id for item in name_sorted.items] == [processed.id, uploaded.id]


async def test_last_run_filters_include_nulls_in_upper_bound(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await build_documents_fixture(session)

    service = DocumentsService(session=session, settings=settings)

    filters = DocumentFilters(last_run_to=datetime.now(tz=UTC))
    order_by_default = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by_default,
        filters=filters,
        actor=uploader,
    )

    returned_ids = {item.id for item in result.items}
    assert uploaded.id in returned_ids  # null last_run_at treated as "never"
    assert processed.id in returned_ids


async def test_sorting_last_run_places_nulls_last(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await build_documents_fixture(session)

    service = DocumentsService(session=session, settings=settings)

    order_by_last_run = resolve_sort(
        ["-last_run_at"],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by_last_run,
        filters=DocumentFilters(),
        actor=uploader,
    )

    assert [item.id for item in result.items] == [processed.id, uploaded.id]


async def test_list_documents_includes_last_run_message(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await build_documents_fixture(session)
    run = await seed_failed_run(
        session,
        workspace_id=workspace.id,
        document_id=processed.id,
        uploader_id=uploader.id,
    )

    service = DocumentsService(session=session, settings=settings)
    order_by = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=25,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(),
        actor=uploader,
    )

    processed_record = next(item for item in result.items if item.id == processed.id)
    assert processed_record.last_run is not None
    assert processed_record.last_run.run_id == run.id
    assert processed_record.last_run.status == RunStatus.FAILED
    assert processed_record.last_run.message == "Request failed with status 404"
    assert processed_record.last_run.run_at == run.completed_at

    uploaded_record = next(item for item in result.items if item.id == uploaded.id)
    assert uploaded_record.last_run is None
