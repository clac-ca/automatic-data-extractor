from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
import pytest

from ade_api.common.cursor_listing import (
    cursor_field,
    cursor_field_nulls_last,
    encode_cursor,
    paginate_sequence_cursor,
    parse_datetime,
    parse_str,
    resolve_cursor_sort_sequence,
)


@dataclass
class _CursorItem:
    id: str
    updated_at: datetime | None


def test_paginate_sequence_cursor_rejects_invalid_null_rank() -> None:
    cursor_fields = {
        "id": cursor_field(lambda item: item.id, parse_str),
        "updatedAt": cursor_field_nulls_last(
            lambda item: item.updated_at,
            parse_datetime,
        ),
    }
    resolved_sort = resolve_cursor_sort_sequence(
        ["updatedAt"],
        cursor_fields=cursor_fields,
        default=["updatedAt"],
    )
    bad_cursor = encode_cursor(
        sort=resolved_sort.tokens,
        values=["oops", "2025-01-01T00:00:00Z", "item-1"],
    )
    items = [
        _CursorItem(id="item-1", updated_at=datetime(2025, 1, 1, tzinfo=UTC)),
        _CursorItem(id="item-2", updated_at=None),
    ]

    with pytest.raises(HTTPException):
        paginate_sequence_cursor(
            items,
            resolved_sort=resolved_sort,
            limit=10,
            cursor=bad_cursor,
            include_total=False,
            changes_cursor=None,
        )
