from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from ade_api.common.list_filters import (
    FilterJoinOperator,
    parse_filter_items,
    prepare_filters,
)
from ade_api.features.documents.filters import (
    DOCUMENT_FILTER_REGISTRY,
    apply_document_filters,
)
from ade_db.models import File


def test_relative_today_filter_with_unhashable_entry_returns_http_error() -> None:
    raw = (
        '[{"id":"createdAt","operator":"isRelativeToToday",'
        '"value":[{"unexpected":true},"2024-05-01T00:00:00Z"]}]'
    )

    items = parse_filter_items(raw, max_filters=5, max_raw_length=500)

    with pytest.raises(HTTPException):
        prepare_filters(items, DOCUMENT_FILTER_REGISTRY)


def test_mentioned_user_filter_compiles_to_exists_predicate() -> None:
    raw = (
        '[{"id":"mentionedUserId","operator":"in",'
        '"value":["00000000-0000-0000-0000-000000000001"]}]'
    )

    filters = parse_filter_items(raw, max_filters=5, max_raw_length=500)
    stmt = apply_document_filters(
        select(File.id),
        filters,
        join_operator=FilterJoinOperator.AND,
        q=None,
    )
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))

    assert "file_comment_mentions" in compiled
    assert "file_comments" in compiled
    assert "mentioned_user_id" in compiled
