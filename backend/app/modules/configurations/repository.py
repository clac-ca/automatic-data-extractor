"""Persistence helpers for configuration queries."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Configuration


class ConfigurationsRepository:
    """Query helper responsible for configuration lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_configurations(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        document_type: str | None = None,
    ) -> list[Configuration]:
        """Return configurations ordered by recency."""

        stmt: Select[tuple[Configuration]] = select(Configuration).order_by(
            Configuration.created_at.desc(),
            Configuration.id.desc(),
        )
        if document_type:
            stmt = stmt.where(Configuration.document_type == document_type)
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_configuration(self, configuration_id: str) -> Configuration | None:
        """Return the configuration identified by ``configuration_id`` when available."""

        return await self._session.get(Configuration, configuration_id)

    async def get_active_configuration(
        self, document_type: str
    ) -> Configuration | None:
        """Return the active configuration for ``document_type`` when present."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(
                Configuration.document_type == document_type,
                Configuration.is_active.is_(True),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_configuration_by_version(
        self,
        *,
        document_type: str,
        version: int,
    ) -> Configuration | None:
        """Return the configuration for ``document_type`` at ``version`` when present."""

        stmt: Select[tuple[Configuration]] = (
            select(Configuration)
            .where(
                Configuration.document_type == document_type,
                Configuration.version == version,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()


__all__ = ["ConfigurationsRepository"]
