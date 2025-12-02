"""Persistence helpers for workspace configurations."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.models import Configuration, ConfigurationStatus


class ConfigurationsRepository:
    """Query helpers for configuration metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def base_query(self) -> Select[tuple[Configuration]]:
        return select(Configuration)

    async def get(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
    ) -> Configuration | None:
        stmt = (
            self.base_query()
            .where(
                Configuration.workspace_id == workspace_id,
                Configuration.id == configuration_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_workspace(self, workspace_id: str) -> Sequence[Configuration]:
        stmt = (
            self.base_query()
            .where(Configuration.workspace_id == workspace_id)
            .order_by(Configuration.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, configuration_id: str) -> Configuration | None:
        stmt = self.base_query().where(Configuration.id == configuration_id).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(self, workspace_id: str) -> Configuration | None:
        stmt = (
            self.base_query()
            .where(
                Configuration.workspace_id == workspace_id,
                Configuration.status == ConfigurationStatus.ACTIVE,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["ConfigurationsRepository"]
