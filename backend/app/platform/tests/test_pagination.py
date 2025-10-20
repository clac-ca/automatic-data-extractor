from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from backend.app import get_settings
from backend.app.db.engine import ensure_database_ready
from backend.app.db.session import get_sessionmaker
from backend.app.features.workspaces.models import Workspace
from backend.app.platform.pagination import paginate

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
        envelope = await paginate(
            session,
            query,
            page=1,
            per_page=2,
            order_by=(
                Workspace.created_at.asc(),
                Workspace.id.asc(),
            ),
            include_total=True,
        )

        assert envelope["page"] == 1
        assert envelope["per_page"] == 2
        assert envelope["has_next"] is True
        assert envelope["total"] == 3
        assert [item.slug for item in envelope["items"]] == [
            records[0].slug,
            records[1].slug,
        ]
