"""Persistence helpers for configuration build metadata and logs."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.sql import Select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.pagination import Page, paginate_sql
from ade_api.core.models import Build, BuildStatus

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
        statuses: Sequence[BuildStatus] | None,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> Page[Build]:
        """Return paginated builds for ``configuration_id``."""

        stmt: Select = select(Build).where(
            Build.workspace_id == workspace_id,
            Build.configuration_id == configuration_id,
        )
        if statuses:
            stmt = stmt.where(Build.status.in_(statuses))

        return await paginate_sql(
            self._session,
            stmt,
            page=page,
            page_size=page_size,
            include_total=include_total,
            order_by=[desc(Build.created_at)],
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
