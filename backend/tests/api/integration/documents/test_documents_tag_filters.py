"""Document tag filter tests."""

from __future__ import annotations

import pytest

from ade_api.common.list_filters import FilterItem, FilterJoinOperator, FilterOperator
from ade_api.common.cursor_listing import resolve_cursor_sort
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import CURSOR_FIELDS, DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_storage import build_storage_adapter
from tests.api.integration.documents.helpers import build_tag_filter_fixture

pytestmark = pytest.mark.asyncio


async def test_tag_filters_any_all_not_empty(db_session, settings) -> None:
    workspace, _, doc_all, doc_finance, doc_priority, doc_empty = await build_tag_filter_fixture(
        db_session
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

    any_match = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=order_by,
        include_total=False,
        include_facets=False,
        filters=[
            FilterItem(
                id="tags",
                operator=FilterOperator.IN,
                value=["finance", "priority"],
            )
        ],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )
    any_ids = {item.id for item in any_match.items}
    assert any_ids == {doc_all.id, doc_finance.id, doc_priority.id}

    all_match = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=order_by,
        include_total=False,
        include_facets=False,
        filters=[
            FilterItem(
                id="tags",
                operator=FilterOperator.EQ,
                value="finance",
            ),
            FilterItem(
                id="tags",
                operator=FilterOperator.EQ,
                value="priority",
            ),
        ],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )
    assert {item.id for item in all_match.items} == {doc_all.id}

    not_match = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=order_by,
        include_total=False,
        include_facets=False,
        filters=[
            FilterItem(
                id="tags",
                operator=FilterOperator.NOT_IN,
                value=["priority"],
            )
        ],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )
    not_ids = {item.id for item in not_match.items}
    assert doc_all.id not in not_ids
    assert doc_priority.id not in not_ids
    assert doc_finance.id in not_ids
    assert doc_empty.id in not_ids

    empty_match = service.list_documents(
        workspace_id=workspace.id,
        limit=50,
        cursor=None,
        resolved_sort=order_by,
        include_total=False,
        include_facets=False,
        filters=[FilterItem(id="tags", operator=FilterOperator.IS_EMPTY)],
        join_operator=FilterJoinOperator.AND,
        q=None,
    )
    assert {item.id for item in empty_match.items} == {doc_empty.id}
