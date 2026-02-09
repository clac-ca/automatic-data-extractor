from __future__ import annotations

import pytest
from fastapi import HTTPException

from ade_api.common.list_filters import parse_filter_items, prepare_filters
from ade_api.features.documents.filters import DOCUMENT_FILTER_REGISTRY


def test_relative_today_filter_with_unhashable_entry_returns_http_error() -> None:
    raw = (
        '[{"id":"createdAt","operator":"isRelativeToToday",'
        '"value":[{"unexpected":true},"2024-05-01T00:00:00Z"]}]'
    )

    items = parse_filter_items(raw, max_filters=5, max_raw_length=500)

    with pytest.raises(HTTPException):
        prepare_filters(items, DOCUMENT_FILTER_REGISTRY)
