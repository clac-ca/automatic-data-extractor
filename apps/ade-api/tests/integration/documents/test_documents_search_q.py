"""Document search query tests."""

from __future__ import annotations

import pytest

from ade_api.common.list_filters import FilterJoinOperator
from ade_api.common.sorting import resolve_sort
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from tests.integration.documents.helpers import build_documents_fixture

pytestmark = pytest.mark.asyncio


async def test_list_documents_q_matches_tokens_across_fields(session, settings) -> None:
    workspace, _uploader, _colleague, processed, _uploaded = await build_documents_fixture(session)

    service = DocumentsService(session=session, settings=settings)
    order_by = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )

    result = service.list_documents(
        workspace_id=workspace.id,
        page=1,
        per_page=50,
        order_by=order_by,
        filters=[],
        join_operator=FilterJoinOperator.AND,
        q="alpha finance",
    )

    assert len(result.items) == 1
    assert result.items[0].name == processed.original_filename
