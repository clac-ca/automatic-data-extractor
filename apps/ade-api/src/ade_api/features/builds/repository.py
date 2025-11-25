"""Persistence helpers for configuration build metadata and logs."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Build, BuildLog

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

    async def add_log(self, log: BuildLog) -> BuildLog:
        self._session.add(log)
        await self._session.flush()
        return log

    def logs_query(self) -> Select[tuple[BuildLog]]:
        return select(BuildLog)

    async def list_logs(
        self,
        *,
        build_id: str,
        after_id: int | None = None,
        limit: int = 1000,
    ) -> Sequence[BuildLog]:
        stmt = self.logs_query().where(BuildLog.build_id == build_id)
        if after_id is not None:
            stmt = stmt.where(BuildLog.id > after_id)
        stmt = stmt.order_by(BuildLog.id.asc()).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()
