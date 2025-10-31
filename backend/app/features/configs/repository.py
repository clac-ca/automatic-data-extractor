"""Database helpers for configuration metadata."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Select, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..workspaces.models import Workspace
from .models import Config, ConfigStatus


class ConfigsRepository:
    """Encapsulate SQL queries for configuration metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_workspace(self, workspace_id: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        for_update: bool = False,
    ) -> Config | None:
        stmt: Select[tuple[Config]] = (
            select(Config)
            .options(selectinload(Config.workspace))
            .where(
                Config.id == config_id,
                Config.workspace_id == workspace_id,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_configs(
        self,
        *,
        workspace_id: str,
        statuses: Iterable[ConfigStatus] | None = None,
    ) -> list[Config]:
        stmt = (
            select(Config)
            .options(selectinload(Config.workspace))
            .where(Config.workspace_id == workspace_id)
            .order_by(Config.created_at.desc())
        )
        if statuses:
            stmt = stmt.where(Config.status.in_(tuple(statuses)))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_config(
        self,
        *,
        workspace_id: str,
        title: str,
        note: str | None,
        status: ConfigStatus = ConfigStatus.INACTIVE,
        version: str = "0.0.1",
        created_by: str | None = None,
    ) -> Config:
        config = Config(
            workspace_id=workspace_id,
            title=title,
            note=note,
            status=status,
            version=version,
            created_by=created_by,
        )
        self._session.add(config)
        await self._session.flush()
        await self._session.refresh(config)
        return config

    async def delete_config(self, config: Config) -> None:
        await self._session.delete(config)

    async def get_active_config(self, workspace_id: str) -> Config | None:
        stmt = (
            select(Config)
            .options(selectinload(Config.workspace))
            .where(
                Config.workspace_id == workspace_id,
                Config.status == ConfigStatus.ACTIVE,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def deactivate_all(self, workspace_id: str) -> None:
        stmt = (
            update(Config)
            .where(
                Config.workspace_id == workspace_id,
                Config.status == ConfigStatus.ACTIVE,
            )
            .values(
                status=ConfigStatus.INACTIVE,
                activated_at=None,
                activated_by=None,
            )
        )
        await self._session.execute(stmt)

    async def set_workspace_active_config(
        self, *, workspace_id: str, config_id: str | None
    ) -> None:
        stmt = (
            update(Workspace)
            .where(Workspace.id == workspace_id)
            .values(active_config_id=config_id)
        )
        await self._session.execute(stmt)

    async def clear_workspace_configs(self, workspace_id: str) -> None:
        await self._session.execute(
            delete(Config).where(Config.workspace_id == workspace_id)
        )


__all__ = ["ConfigsRepository"]
