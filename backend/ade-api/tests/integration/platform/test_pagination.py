from __future__ import annotations

import uuid

from sqlalchemy import select

from ade_api.common.cursor_listing import (
    cursor_field,
    paginate_query_cursor,
    parse_str,
    parse_uuid,
    resolve_cursor_sort,
)
from ade_db.models import Workspace


def _resolve_workspace_sort():
    sort_fields = {
        "slug": (Workspace.slug.asc(), Workspace.slug.desc()),
    }
    cursor_fields = {
        "id": cursor_field(lambda item: item.id, parse_uuid),
        "slug": cursor_field(lambda item: item.slug, parse_str),
    }
    return resolve_cursor_sort(
        [],
        allowed=sort_fields,
        cursor_fields=cursor_fields,
        default=["slug"],
        id_field=(Workspace.id.asc(), Workspace.id.desc()),
    )


def test_paginate_cursor_returns_meta_and_next_cursor(db_session) -> None:
    suffix = uuid.uuid4().hex[:8]
    records = [
        Workspace(name=f"Workspace {index}", slug=f"pagination-{suffix}-{index}") for index in range(3)
    ]
    db_session.add_all(records)
    db_session.commit()

    query = select(Workspace).where(Workspace.slug.like(f"pagination-{suffix}-%"))
    resolved_sort = _resolve_workspace_sort()
    page = paginate_query_cursor(
        db_session,
        query,
        resolved_sort=resolved_sort,
        limit=2,
        cursor=None,
        include_total=True,
        changes_cursor="0",
    )

    assert page.meta.limit == 2
    assert page.meta.has_more is True
    assert page.meta.next_cursor
    assert page.meta.total_included is True
    assert page.meta.total_count == 3
    assert page.meta.changes_cursor == "0"

    expected_slugs = sorted([record.slug for record in records])
    assert [item.slug for item in page.items] == expected_slugs[:2]

    next_page = paginate_query_cursor(
        db_session,
        query,
        resolved_sort=resolved_sort,
        limit=2,
        cursor=page.meta.next_cursor,
        include_total=False,
        changes_cursor="0",
    )

    assert next_page.meta.has_more is False
    assert next_page.meta.next_cursor is None
    assert next_page.meta.total_included is False
    assert next_page.meta.total_count is None
    assert [item.slug for item in next_page.items] == expected_slugs[2:]
