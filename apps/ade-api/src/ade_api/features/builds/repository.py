"""Persistence helpers for configuration build metadata and logs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.listing import ListPage, paginate_query
from ade_api.common.types import OrderBy
from ade_api.models import Build, BuildStatus

from .filters import apply_build_filters

__all__ = [
    "BuildsRepository",
]


class BuildsRepository:
    """Encapsulate read/write operations for build resources."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, build_id: UUID) -> Build | None:
        return await self._session.get(Build, build_id)

    async def add(self, build: Build) -> None:
        self._session.add(build)
        await self._session.flush()

    async def list_by_configuration(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        order_by: OrderBy,
        page: int,
        per_page: int,
    ) -> ListPage[Build]:
        """Return paginated builds for ``configuration_id``."""

        stmt: Select = select(Build).where(
            Build.workspace_id == workspace_id,
            Build.configuration_id == configuration_id,
        )
        stmt = apply_build_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )

        return await paginate_query(
            self._session,
            stmt,
            page=page,
            per_page=per_page,
            order_by=order_by,
            changes_cursor="0",
        )

    async def get_ready_by_fingerprint(
        self,
        *,
        configuration_id: UUID,
        fingerprint: str,
    ) -> Build | None:
        stmt = (
            select(Build)
            .where(
                Build.configuration_id == configuration_id,
                Build.status == BuildStatus.READY,
                Build.fingerprint == fingerprint,
            )
            .order_by(Build.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_fingerprint(
        self,
        *,
        configuration_id: UUID,
        fingerprint: str,
    ) -> Build | None:
        stmt = (
            select(Build)
            .where(
                Build.configuration_id == configuration_id,
                Build.fingerprint == fingerprint,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_inflight_by_fingerprint(
        self,
        *,
        configuration_id: UUID,
        fingerprint: str,
    ) -> Build | None:
        stmt = (
            select(Build)
            .where(
                Build.configuration_id == configuration_id,
                Build.status.in_([BuildStatus.QUEUED, BuildStatus.BUILDING]),
                Build.fingerprint == fingerprint,
            )
            .order_by(Build.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_latest_inflight(self, *, configuration_id: UUID) -> Build | None:
        stmt = (
            select(Build)
            .where(
                Build.configuration_id == configuration_id,
                Build.status.in_([BuildStatus.QUEUED, BuildStatus.BUILDING]),
            )
            .order_by(Build.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()
