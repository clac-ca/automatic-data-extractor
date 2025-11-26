from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ade_api.features.builds.builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    BuildStep,
)
from ade_api.features.builds.models import BuildStatus
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.features.builds.service import BuildsService
from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.features.configs.storage import ConfigStorage
from ade_api.features.workspaces.models import Workspace
from ade_api.settings import Settings
from ade_api.shared.core.time import utc_now
from ade_api.shared.db import Base
from ade_api.shared.db.mixins import generate_ulid


@dataclass(slots=True)
class FakeBuilder:
    events: list[BuilderEvent]

    async def build_stream(
        self,
        *,
        build_id: str,
        workspace_id: str,
        configuration_id: str,
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
def service_factory(
    tmp_path: Path,
) -> Callable[
    [AsyncSession, FakeBuilder | None, Callable[[], datetime]],
    BuildsService,
]:
    def _factory(
        session: AsyncSession,
        builder: FakeBuilder | None = None,
        now: Callable[[], datetime] = utc_now,
    ) -> BuildsService:
        base_settings = Settings()
        workspaces_dir = tmp_path / "workspaces"
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(parents=True, exist_ok=True)
        (engine_dir / "pyproject.toml").write_text(
            """
[project]
name = "ade-engine"
version = "0.2.0"
""".strip(),
            encoding="utf-8",
        )
        pip_cache_dir = tmp_path / "pip-cache"
        settings = base_settings.model_copy(
            update={
                "workspaces_dir": workspaces_dir,
                "configs_dir": workspaces_dir,
                "pip_cache_dir": pip_cache_dir,
                "engine_spec": str(engine_dir),
            }
        )
        templates_root = tmp_path / "templates"
        templates_root.mkdir(parents=True, exist_ok=True)
        storage = ConfigStorage(
            templates_root=templates_root,
            settings=settings,
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
    configuration_id = generate_ulid()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
        configuration_version=1,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()
    return workspace, configuration


async def test_prepare_build_reuses_active(
    session: AsyncSession,
    tmp_path: Path,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    builder = FakeBuilder(events=[])
    service = service_factory(session, builder=builder)

    config_path = service.storage.config_path(workspace.id, configuration.id)
    config_path.mkdir(parents=True, exist_ok=True)

    configuration.build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
    configuration.built_configuration_version = configuration.configuration_version  # type: ignore[attr-defined]
    configuration.built_content_digest = configuration.content_digest  # type: ignore[attr-defined]
    configuration.engine_spec = service.settings.engine_spec  # type: ignore[attr-defined]
    configuration.engine_version = "0.2.0"  # type: ignore[attr-defined]
    configuration.python_interpreter = service.settings.python_bin  # type: ignore[attr-defined]
    configuration.python_version = "3.12.1"  # type: ignore[attr-defined]
    configuration.last_build_finished_at = utc_now()  # type: ignore[attr-defined]
    await session.commit()

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
    )

    assert context.should_run is False
    assert build.status is BuildStatus.ACTIVE
    assert build.summary == "Reused existing build"


@pytest.mark.asyncio()
async def test_stream_build_success(
    session: AsyncSession,
    tmp_path: Path,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    builder = FakeBuilder(
        events=[
            BuilderStepEvent(step=BuildStep.CREATE_VENV, message="venv"),
            BuilderLogEvent(message="log 1"),
            BuilderStepEvent(step=BuildStep.INSTALL_ENGINE, message="install"),
            BuilderLogEvent(message="log 2"),
            BuilderArtifactsEvent(
                artifacts=BuildArtifacts(python_version="3.12.1", engine_version="0.2.0")
            ),
        ]
    )
    service = service_factory(session, builder=builder)

    config_path = service.storage.config_path(workspace.id, configuration.id)
    config_path.mkdir(parents=True, exist_ok=True)

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=True, wait=False),
    )
    events = []
    async for event in service.stream_build(
        context=context,
        options=BuildCreateOptions(force=True, wait=False),
    ):
        events.append(event)

    refreshed = await service.get_build(build.id)
    assert refreshed is not None
    assert refreshed.status is BuildStatus.ACTIVE
    assert refreshed.summary == "Build succeeded"
    logs = await service.get_logs(build_id=build.id)
    assert [entry.message for entry in logs.entries] == ["log 1", "log 2"]
    assert logs.next_after_id is None
    assert any(getattr(evt, "type", "") == "build.completed" for evt in events)
