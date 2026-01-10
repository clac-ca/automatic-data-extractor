from __future__ import annotations

import uuid

from sqlalchemy import select

from ade_api.common.listing import paginate_query
from ade_api.models import Workspace


def test_paginate_returns_canonical_envelope(session) -> None:
    suffix = uuid.uuid4().hex[:8]
    records = [
        Workspace(name=f"Workspace {index}", slug=f"pagination-{suffix}-{index}") for index in range(3)
    ]
    session.add_all(records)
    session.commit()

    query = select(Workspace).where(Workspace.slug.like(f"pagination-{suffix}-%"))
    page = paginate_query(
        session,
        query,
        page=1,
        per_page=2,
        order_by=(
            Workspace.created_at.asc(),
            Workspace.id.asc(),
        ),
    )

    assert page.page == 1
    assert page.per_page == 2
    assert page.page_count == 2
    assert page.total == 3
    assert page.changes_cursor == "0"
    assert [item.slug for item in page.items] == [
        records[0].slug,
        records[1].slug,
    ]
