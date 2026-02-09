"""Document search query tests."""

from __future__ import annotations

import pytest

from ade_api.common.list_filters import FilterJoinOperator
from ade_api.common.cursor_listing import resolve_cursor_sort
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import CURSOR_FIELDS, DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_api.infra.storage import build_storage_adapter
from tests.integration.documents.helpers import build_documents_fixture

pytestmark = pytest.mark.asyncio


async def test_list_documents_q_matches_tokens_across_fields(db_session, settings) -> None:
    workspace, _uploader, _colleague, processed, _uploaded = await build_documents_fixture(
        db_session
    )

    storage = build_storage_adapter(settings)
    service = DocumentsService(session=db_session, settings=settings, storage=storage)
    resolved_sort = resolve_cursor_sort(
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
        resolved_sort=resolved_sort,
        include_total=False,
        include_facets=False,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q="alpha finance",
    )

    assert len(result.items) == 1
    assert result.items[0].name == processed.name
