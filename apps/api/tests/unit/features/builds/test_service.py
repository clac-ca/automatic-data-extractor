import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.app.features.builds.builder import (
    BuildArtifacts,
    BuildStep,
    BuilderArtifactsEvent,
    BuilderEvent,
    BuilderLogEvent,
    BuilderStepEvent,
)
from apps.api.app.features.builds.models import BuildStatus, ConfigurationBuild, ConfigurationBuildStatus
from apps.api.app.features.builds.schemas import BuildCreateOptions
from apps.api.app.features.builds.service import BuildExecutionContext, BuildsService
from apps.api.app.features.configs.models import Configuration, ConfigurationStatus
from apps.api.app.features.configs.storage import ConfigStorage
from apps.api.app.features.workspaces.models import Workspace
from apps.api.app.settings import Settings
from apps.api.app.shared.core.time import utc_now
from apps.api.app.shared.db import Base
from apps.api.app.shared.db.mixins import generate_ulid


@dataclass(slots=True)
class FakeBuilder:
    events: list[BuilderEvent]

    async def build_stream(
        self,
        *,
        build_id: str,
        workspace_id: str,
        config_id: str,
        target_path: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
    ) -> AsyncIterator[BuilderEvent]:
        target_path.mkdir(parents=True, exist_ok=True)
        for event in self.events:
            yield event


class TimeStub:
    def __init__(self, initial: datetime | None = None) -> None:
        self.current = initial or datetime.now(tz=UTC)

    def advance(self, delta: timedelta) -> None:
        self.current += delta

    def __call__(self) -> datetime:
        return self.current


@pytest.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture()
def service_factory(tmp_path: Path) -> Callable[[AsyncSession, FakeBuilder | None, Callable[[], datetime]], BuildsService]:
    def _factory(
        session: AsyncSession,
        builder: FakeBuilder | None = None,
        now: Callable[[], datetime] = utc_now,
    ) -> BuildsService:
        base_settings = Settings()
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(parents=True, exist_ok=True)
        (engine_dir / "pyproject.toml").write_text(
            """
[project]
name = "ade-engine"
version = "0.1.0"
""".strip(),
            encoding="utf-8",
        )
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir(parents=True, exist_ok=True)
        venvs_dir = tmp_path / "venvs"
        pip_cache_dir = tmp_path / "pip-cache"
        settings = base_settings.model_copy(
            update={
                "configs_dir": configs_dir,
                "venvs_dir": venvs_dir,
                "pip_cache_dir": pip_cache_dir,
                "engine_spec": str(engine_dir),
            }
        )
        templates_root = tmp_path / "templates"
        templates_root.mkdir(parents=True, exist_ok=True)
        storage = ConfigStorage(
            templates_root=templates_root,
            configs_root=settings.configs_dir,
        )
        builder = builder or FakeBuilder(events=[])
        return BuildsService(
            session=session,
            settings=settings,
            storage=storage,
            builder=builder,
            now=now,
        )

    return _factory


async def _create_configuration(
    session: AsyncSession,
) -> tuple[Workspace, Configuration]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_ulid().lower()}")
    session.add(workspace)
    await session.flush()
    configuration = Configuration(
        workspace_id=workspace.id,
        config_id=generate_ulid(),
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
        config_version=1,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()
    return workspace, configuration


async def test_prepare_build_reuses_active(session: AsyncSession, tmp_path: Path, service_factory) -> None:
    workspace, configuration = await _create_configuration(session)
    builder = FakeBuilder(events=[])
    service = service_factory(session, builder=builder)

    config_path = service.storage.config_path(workspace.id, configuration.config_id)
    config_path.mkdir(parents=True, exist_ok=True)

    pointer = ConfigurationBuild(
        workspace_id=workspace.id,
        config_id=configuration.config_id,
        configuration_id=configuration.id,
        build_id=generate_ulid(),
        status=ConfigurationBuildStatus.ACTIVE,
        venv_path=str(tmp_path / "venvs" / workspace.id / configuration.config_id / "existing"),
        config_version=configuration.config_version,
        content_digest=configuration.content_digest,
        engine_spec=service.settings.engine_spec,
        engine_version="0.1.0",
        python_interpreter=service.settings.python_bin,
        built_at=utc_now(),
    )
    session.add(pointer)
    await session.commit()

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        config_id=configuration.config_id,
        options=BuildCreateOptions(force=False, wait=False),
    )

    assert context.should_run is False
    assert build.status is BuildStatus.ACTIVE
    assert build.summary == "Reused existing build"
    assert build.build_ref == pointer.build_id


@pytest.mark.asyncio()
async def test_stream_build_success(session: AsyncSession, tmp_path: Path, service_factory) -> None:
    workspace, configuration = await _create_configuration(session)
    builder = FakeBuilder(
        events=[
            BuilderStepEvent(step=BuildStep.CREATE_VENV, message="venv"),
            BuilderLogEvent(message="log 1"),
            BuilderStepEvent(step=BuildStep.INSTALL_ENGINE, message="install"),
            BuilderLogEvent(message="log 2"),
            BuilderArtifactsEvent(
                artifacts=BuildArtifacts(python_version="3.12.1", engine_version="0.1.0")
            ),
        ]
    )
    service = service_factory(session, builder=builder)

    config_path = service.storage.config_path(workspace.id, configuration.config_id)
    config_path.mkdir(parents=True, exist_ok=True)

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        config_id=configuration.config_id,
        options=BuildCreateOptions(force=True, wait=False),
    )
    events = []
    async for event in service.stream_build(context=context, options=BuildCreateOptions(force=True, wait=False)):
        events.append(event)

    refreshed = await service.get_build(build.id)
    assert refreshed is not None
    assert refreshed.status is BuildStatus.ACTIVE
    assert refreshed.summary == "Build succeeded"
    logs = await service.get_logs(build_id=build.id)
    assert [entry.message for entry in logs.entries] == ["log 1", "log 2"]
    assert logs.next_after_id is None
    assert any(getattr(evt, "type", "") == "build.completed" for evt in events)
