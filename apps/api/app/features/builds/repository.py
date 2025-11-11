"""Persistence helpers for configuration build metadata."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BuildStatus, ConfigurationBuild

__all__ = ["ConfigurationBuildsRepository"]


class ConfigurationBuildsRepository:
    """Read/write helpers encapsulating build-specific SQL operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def base_query(self) -> Select[tuple[ConfigurationBuild]]:
        return select(ConfigurationBuild)

    async def get_build(
        self,
        *,
        workspace_id: str,
        config_id: str,
        build_id: str,
    ) -> ConfigurationBuild | None:
        stmt = (
            self.base_query()
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.build_id == build_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest(
        self, *, workspace_id: str, config_id: str
    ) -> ConfigurationBuild | None:
        stmt = (
            self.base_query()
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
            )
            .order_by(ConfigurationBuild.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(
        self, *, workspace_id: str, config_id: str
    ) -> ConfigurationBuild | None:
        stmt = (
            self.base_query()
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.status == BuildStatus.ACTIVE.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_building(
        self, *, workspace_id: str, config_id: str
    ) -> ConfigurationBuild | None:
        stmt = (
            self.base_query()
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.status == BuildStatus.BUILDING.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_inactive(
        self, *, workspace_id: str, config_id: str
    ) -> Sequence[ConfigurationBuild]:
        stmt = (
            self.base_query()
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.status.in_(
                    [BuildStatus.INACTIVE.value, BuildStatus.FAILED.value]
                ),
            )
            .order_by(ConfigurationBuild.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def deactivate_all(
        self, *, workspace_id: str, config_id: str, exclude_build_id: str
    ) -> None:
        stmt = (
            update(ConfigurationBuild)
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.build_id != exclude_build_id,
                ConfigurationBuild.status == BuildStatus.ACTIVE.value,
            )
            .values(status=BuildStatus.INACTIVE.value)
        )
        await self._session.execute(stmt)

    async def mark_failed(
        self,
        *,
        workspace_id: str,
        config_id: str,
        build_id: str,
        error: str,
        finished_at: datetime,
    ) -> None:
        stmt = (
            update(ConfigurationBuild)
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.build_id == build_id,
            )
            .values(
                status=BuildStatus.FAILED.value,
                built_at=finished_at,
                error=error,
            )
        )
        await self._session.execute(stmt)

    async def update_active(
        self,
        *,
        workspace_id: str,
        config_id: str,
        build_id: str,
        built_at: datetime,
        python_version: str,
        engine_version: str,
        venv_path: str,
    ) -> None:
        stmt = (
            update(ConfigurationBuild)
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.build_id == build_id,
            )
            .values(
                status=BuildStatus.ACTIVE.value,
                built_at=built_at,
                last_used_at=built_at,
                python_version=python_version,
                engine_version=engine_version,
                error=None,
                venv_path=venv_path,
            )
        )
        await self._session.execute(stmt)

    async def update_last_used(
        self,
        *,
        workspace_id: str,
        config_id: str,
        build_id: str,
        last_used_at: datetime,
    ) -> None:
        stmt = (
            update(ConfigurationBuild)
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.build_id == build_id,
            )
            .values(last_used_at=last_used_at)
        )
        await self._session.execute(stmt)

    async def delete_build(
        self,
        *,
        workspace_id: str,
        config_id: str,
        build_id: str,
    ) -> None:
        stmt = (
            delete(ConfigurationBuild)
            .where(
                ConfigurationBuild.workspace_id == workspace_id,
                ConfigurationBuild.config_id == config_id,
                ConfigurationBuild.build_id == build_id,
            )
        )
        await self._session.execute(stmt)
