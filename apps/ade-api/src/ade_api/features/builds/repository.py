"""Persistence helpers for configuration build metadata and logs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Build, BuildStatus

__all__ = [
    "BuildsRepository",
]


class BuildsRepository:
    """Encapsulate read/write operations for build resources."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, build_id: str) -> Build | None:
        return await self._session.get(Build, build_id)

    async def add(self, build: Build) -> None:
        self._session.add(build)
        await self._session.flush()

    async def get_active_by_fingerprint(
        self,
        *,
        configuration_id: str,
        fingerprint: str,
    ) -> Build | None:
        stmt = (
            select(Build)
            .where(
                Build.configuration_id == configuration_id,
                Build.status == BuildStatus.ACTIVE,
                Build.fingerprint == fingerprint,
            )
            .order_by(Build.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_latest_inflight(self, *, configuration_id: str) -> Build | None:
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
