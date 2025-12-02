from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from ade_api.core.models import Workspace
from ade_api.settings import get_settings
from ade_api.infra.db.engine import ensure_database_ready
from ade_api.infra.db.session import get_sessionmaker
from ade_api.common.pagination import paginate_sql

pytestmark = pytest.mark.asyncio


async def test_paginate_returns_envelope_with_optional_total() -> None:
    settings = get_settings()
    await ensure_database_ready(settings)
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        suffix = uuid.uuid4().hex[:8]
        records = [
            Workspace(name=f"Workspace {index}", slug=f"pagination-{suffix}-{index}")
            for index in range(3)
        ]
        session.add_all(records)
        await session.commit()

        query = select(Workspace).where(
            Workspace.slug.like(f"pagination-{suffix}-%")
        )
        page = await paginate_sql(
            session,
            query,
            page=1,
            page_size=2,
            order_by=(
                Workspace.created_at.asc(),
                Workspace.id.asc(),
            ),
            include_total=True,
        )

        assert page.page == 1
        assert page.page_size == 2
        assert page.has_next is True
        assert page.total == 3
        assert [item.slug for item in page.items] == [
            records[0].slug,
            records[1].slug,
        ]
