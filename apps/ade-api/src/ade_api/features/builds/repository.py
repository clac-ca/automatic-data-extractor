"""Persistence helpers for configuration build metadata and logs."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Build

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
