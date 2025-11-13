"""Persistence helpers for configuration build metadata and logs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Build,
    BuildLog,
    ConfigurationBuild,
    ConfigurationBuildStatus,
)

__all__ = [
    "BuildsRepository",
    "ConfigurationBuildsRepository",
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


class ConfigurationBuildsRepository:
    """Read/write helpers encapsulating legacy configuration build rows."""

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
                ConfigurationBuild.status == ConfigurationBuildStatus.ACTIVE,
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
                ConfigurationBuild.status == ConfigurationBuildStatus.BUILDING,
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
                    [ConfigurationBuildStatus.INACTIVE, ConfigurationBuildStatus.FAILED]
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
                ConfigurationBuild.status == ConfigurationBuildStatus.ACTIVE,
            )
            .values(status=ConfigurationBuildStatus.INACTIVE)
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
                status=ConfigurationBuildStatus.FAILED,
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
                status=ConfigurationBuildStatus.ACTIVE,
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

