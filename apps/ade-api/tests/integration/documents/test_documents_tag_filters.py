"""Document tag filter tests."""

from __future__ import annotations

import pytest

from ade_api.common.sorting import resolve_sort
from ade_api.features.documents.filters import DocumentFilters
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from tests.integration.documents.helpers import build_tag_filter_fixture

pytestmark = pytest.mark.asyncio


async def test_tag_filters_any_all_not_empty(session, settings) -> None:
    workspace, uploader, doc_all, doc_finance, doc_priority, doc_empty = await build_tag_filter_fixture(
        session
    )

    service = DocumentsService(session=session, settings=settings)
    order_by = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )

    any_match = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(tags={"finance", "priority"}),
        actor=uploader,
    )
    any_ids = {item.id for item in any_match.items}
    assert any_ids == {doc_all.id, doc_finance.id, doc_priority.id}

    all_match = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(tags={"finance", "priority"}, tags_match="all"),
        actor=uploader,
    )
    assert {item.id for item in all_match.items} == {doc_all.id}

    not_match = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(tags_not={"priority"}),
        actor=uploader,
    )
    not_ids = {item.id for item in not_match.items}
    assert doc_all.id not in not_ids
    assert doc_priority.id not in not_ids
    assert doc_finance.id in not_ids
    assert doc_empty.id in not_ids

    empty_match = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(tags_empty=True),
        actor=uploader,
    )
    assert {item.id for item in empty_match.items} == {doc_empty.id}
