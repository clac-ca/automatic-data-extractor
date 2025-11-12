"""Service encapsulating configuration build orchestration."""

from __future__ import annotations

import asyncio
import shutil
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.features.configs.exceptions import ConfigurationNotFoundError
from apps.api.app.features.configs.repository import ConfigurationsRepository
from apps.api.app.features.configs.storage import ConfigStorage
from apps.api.app.settings import Settings
from apps.api.app.shared.core.time import utc_now
from apps.api.app.shared.db.mixins import generate_ulid

from .builder import VirtualEnvironmentBuilder
from .exceptions import (
    BuildAlreadyInProgressError,
    BuildExecutionError,
    BuildNotFoundError,
)
from .models import BuildStatus, ConfigurationBuild
from .repository import ConfigurationBuildsRepository

__all__ = [
    "BuildEnsureMode",
    "BuildEnsureResult",
    "BuildsService",
]


class BuildEnsureMode(str, Enum):
    """Identify caller expectations for ensure_build."""

    INTERACTIVE = "interactive"
    BLOCKING = "blocking"


@dataclass(slots=True)
class BuildEnsureResult:
    """Result returned by ``ensure_build`` attempts."""

    status: BuildStatus
    build: ConfigurationBuild | None
    just_built: bool = False


class BuildsService:
    """Coordinate build rows, filesystem state, and dedupe semantics."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        storage: ConfigStorage,
        builder: VirtualEnvironmentBuilder | None = None,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._builder = builder or VirtualEnvironmentBuilder()
        self._configs = ConfigurationsRepository(session)
        self._repository = ConfigurationBuildsRepository(session)
        self._now = now

    async def get_active_build(
        self, *, workspace_id: str, config_id: str
    ) -> ConfigurationBuild:
        build = await self._repository.get_active(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        if build is None:
            raise BuildNotFoundError(
                f"No active build for workspace={workspace_id} config={config_id}"
            )
        return build

    async def ensure_build(
        self,
        *,
        workspace_id: str,
        config_id: str,
        force: bool = False,
        mode: BuildEnsureMode = BuildEnsureMode.INTERACTIVE,
    ) -> BuildEnsureResult:
        configuration = await self._configs.get(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(config_id)

        config_path = await self._storage.ensure_config_path(
            workspace_id=workspace_id,
            config_id=config_id,
        )

        python_interpreter = self._settings.python_bin or sys.executable
        python_interpreter = str(Path(python_interpreter).resolve())
        engine_spec = self._settings.engine_spec
        engine_version_hint = self._resolve_engine_version(engine_spec)
        ttl = self._settings.build_ttl

        await self._heal_stale_builder(workspace_id=workspace_id, config_id=config_id)

        active = await self._repository.get_active(
            workspace_id=workspace_id,
            config_id=config_id,
        )

        if active and active.status != BuildStatus.ACTIVE:
            active = None

        should_rebuild = force or active is None
        if active is not None and not should_rebuild:
            should_rebuild = any(
                [
                    active.config_version != configuration.config_version,
                    active.content_digest != configuration.content_digest,
                    active.engine_version != engine_version_hint,
                    active.engine_spec != engine_spec,
                    active.python_interpreter != python_interpreter,
                    ttl is not None
                    and active.built_at is not None
                    and active.built_at + ttl <= self._now(),
                ]
            )

        if not should_rebuild and active is not None:
            await self._repository.update_last_used(
                workspace_id=workspace_id,
                config_id=config_id,
                build_id=active.build_id,
                last_used_at=self._now(),
            )
            return BuildEnsureResult(status=BuildStatus.ACTIVE, build=active)

        building = await self._repository.get_building(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        if building is not None:
            if mode is BuildEnsureMode.BLOCKING:
                return await self._wait_for_build(
                    workspace_id=workspace_id,
                    config_id=config_id,
                    timeout=self._settings.build_ensure_wait,
                )
            return BuildEnsureResult(status=BuildStatus.BUILDING, build=None)

        build_id = generate_ulid()
        target_path = (
            self._settings.venvs_dir
            / workspace_id
            / config_id
            / build_id
        )
        expires_at = (
            self._now() + ttl if ttl is not None else None
        )

        record = ConfigurationBuild(
            workspace_id=workspace_id,
            config_id=config_id,
            configuration_id=configuration.id,
            build_id=build_id,
            status=BuildStatus.BUILDING,
            venv_path=str(target_path),
            config_version=configuration.config_version,
            content_digest=configuration.content_digest,
            engine_version=engine_version_hint,
            engine_spec=engine_spec,
            python_version=None,
            python_interpreter=python_interpreter,
            started_at=self._now(),
            built_at=None,
            expires_at=expires_at,
            last_used_at=None,
            error=None,
        )
        self._session.add(record)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            if mode is BuildEnsureMode.BLOCKING:
                return await self._wait_for_build(
                    workspace_id=workspace_id,
                    config_id=config_id,
                    timeout=self._settings.build_ensure_wait,
                )
            return BuildEnsureResult(status=BuildStatus.BUILDING, build=None)

        try:
            artifacts = await self._builder.build(
                build_id=build_id,
                workspace_id=workspace_id,
                config_id=config_id,
                target_path=target_path,
                config_path=config_path,
                engine_spec=engine_spec,
                pip_cache_dir=self._settings.pip_cache_dir,
                python_bin=python_interpreter,
                timeout=self._settings.build_timeout.total_seconds(),
            )
        except BuildExecutionError as exc:
            await self._repository.mark_failed(
                workspace_id=workspace_id,
                config_id=config_id,
                build_id=build_id,
                error=str(exc),
                finished_at=self._now(),
            )
            await self._session.commit()
            raise

        built_at = self._now()
        await self._repository.deactivate_all(
            workspace_id=workspace_id,
            config_id=config_id,
            exclude_build_id=build_id,
        )
        await self._repository.update_active(
            workspace_id=workspace_id,
            config_id=config_id,
            build_id=build_id,
            built_at=built_at,
            python_version=artifacts.python_version,
            engine_version=artifacts.engine_version,
            venv_path=str(target_path),
        )
        await self._session.commit()

        await self._prune_inactive(
            workspace_id=workspace_id,
            config_id=config_id,
        )

        active = await self._repository.get_active(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        return BuildEnsureResult(status=BuildStatus.ACTIVE, build=active, just_built=True)

    async def delete_active_build(
        self, *, workspace_id: str, config_id: str
    ) -> None:
        build = await self._repository.get_active(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        if build is None:
            raise BuildNotFoundError(
                f"No active build for workspace={workspace_id} config={config_id}"
            )
        await self._repository.delete_build(
            workspace_id=workspace_id,
            config_id=config_id,
            build_id=build.build_id,
        )
        await self._session.commit()
        await self._remove_venv(build.venv_path)

    async def _heal_stale_builder(self, *, workspace_id: str, config_id: str) -> None:
        building = await self._repository.get_building(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        if building is None or building.started_at is None:
            return
        timeout = self._settings.build_timeout
        if building.started_at + timeout > self._now():
            return
        await self._repository.mark_failed(
            workspace_id=workspace_id,
            config_id=config_id,
            build_id=building.build_id,
            error="build_timeout",
            finished_at=self._now(),
        )
        await self._session.commit()
        await self._remove_venv(building.venv_path)

    async def _wait_for_build(
        self,
        *,
        workspace_id: str,
        config_id: str,
        timeout: timedelta,
    ) -> BuildEnsureResult:
        deadline = self._now() + timeout
        while self._now() < deadline:
            active = await self._repository.get_active(
                workspace_id=workspace_id,
                config_id=config_id,
            )
            if active is not None:
                await self._repository.update_last_used(
                    workspace_id=workspace_id,
                    config_id=config_id,
                    build_id=active.build_id,
                    last_used_at=self._now(),
                )
                return BuildEnsureResult(status=BuildStatus.ACTIVE, build=active)

            building = await self._repository.get_building(
                workspace_id=workspace_id,
                config_id=config_id,
            )
            if building is None:
                latest = await self._repository.get_latest(
                    workspace_id=workspace_id,
                    config_id=config_id,
                )
                if latest is not None and latest.status == BuildStatus.FAILED:
                    raise BuildExecutionError(
                        latest.error or "build_failed",
                        build_id=latest.build_id,
                    )
            await asyncio.sleep(1)
        raise BuildAlreadyInProgressError(
            f"Build still in progress for workspace={workspace_id} config={config_id}"
        )

    async def _prune_inactive(self, *, workspace_id: str, config_id: str) -> None:
        retention = self._settings.build_retention
        if retention is None:
            return
        threshold = self._now() - retention
        builds = await self._repository.list_inactive(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        pruned = False
        for build in builds:
            built_at = build.built_at or build.started_at or self._now()
            if built_at <= threshold:
                await self._repository.delete_build(
                    workspace_id=workspace_id,
                    config_id=config_id,
                    build_id=build.build_id,
                )
                await self._remove_venv(build.venv_path)
                pruned = True
        if pruned:
            await self._session.commit()

    async def _remove_venv(self, venv_path: str | None) -> None:
        if not venv_path:
            return
        path = Path(venv_path)

        def _remove() -> None:
            shutil.rmtree(path, ignore_errors=True)

        await asyncio.to_thread(_remove)

    def _resolve_engine_version(self, spec: str) -> str | None:
        path = Path(spec)
        if path.exists() and path.is_dir():
            pyproject = path / "pyproject.toml"
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except OSError:
                return None
            return data.get("project", {}).get("version")
        if "==" in spec:
            return spec.split("==", 1)[1]
        return None
