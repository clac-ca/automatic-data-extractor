import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ade_api.features.builds.builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    BuildStep,
)
from ade_api.features.builds.fingerprint import compute_build_fingerprint
from ade_api.core.models import Build, BuildStatus, Configuration, ConfigurationStatus, Workspace
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.features.builds.service import BuildsService
from ade_api.features.configs.storage import ConfigStorage, compute_config_digest
from ade_api.settings import Settings
from ade_api.common.time import utc_now
from ade_api.infra.db import Base
from ade_api.infra.db.mixins import generate_uuid7
from ade_api.infra.storage import build_venv_root


@dataclass(slots=True)
class FakeBuilder:
    events: list[BuilderEvent]

    async def build_stream(
        self,
        *,
        build_id: str,
        workspace_id: str,
        configuration_id: str,
        venv_root: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
        fingerprint: str | None = None,
    ) -> AsyncIterator[BuilderEvent]:
        venv_root.mkdir(parents=True, exist_ok=True)
        for event in self.events:
            yield event


class TrackingBuilder(FakeBuilder):
    def __init__(self) -> None:
        super().__init__(events=[])
        self.invocations = 0

    async def build_stream(
        self,
        *,
        build_id: str,
        workspace_id: str,
        configuration_id: str,
        venv_root: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
        fingerprint: str | None = None,
    ) -> AsyncIterator[BuilderEvent]:
        self.invocations += 1
        async for event in super().build_stream(
            build_id=build_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            venv_root=venv_root,
            config_path=config_path,
            engine_spec=engine_spec,
            pip_cache_dir=pip_cache_dir,
            python_bin=python_bin,
            timeout=timeout,
            fingerprint=fingerprint,
        ):
            yield event


class TimeStub:
    def __init__(self, initial: datetime | None = None) -> None:
        self.current = initial or datetime.now(tz=UTC)

    def advance(self, delta: timedelta) -> None:
        self.current += delta

    def __call__(self) -> datetime:
        return self.current


@pytest_asyncio.fixture()
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
                "venvs_dir": tmp_path / "venvs",
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
    workspace = Workspace(name="Acme", slug=f"acme-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    await session.flush()
    configuration_id = generate_uuid7()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()
    return workspace, configuration


@pytest.mark.asyncio()
async def test_prepare_build_reuses_active(
    session: AsyncSession,
    tmp_path: Path,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    builder = FakeBuilder(events=[])
    service = service_factory(session, builder=builder)

    config_path = service.storage.config_path(workspace.id, configuration.id)
    (config_path / "src" / "ade_config").mkdir(parents=True, exist_ok=True)
    (config_path / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.0.1'\n")
    digest = compute_config_digest(config_path)
    python_version = await service._python_version(service._resolve_python_interpreter())
    engine_version = service._resolve_engine_version(service.settings.engine_spec)
    fingerprint = compute_build_fingerprint(
        config_digest=digest,
        engine_spec=service.settings.engine_spec,
        engine_version=engine_version,
        python_version=python_version,
        python_bin=service._resolve_python_interpreter(),
        extra={},
    )

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.READY,
        created_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
        exit_code=0,
        fingerprint=fingerprint,
        config_digest=digest,
        engine_spec=service.settings.engine_spec,
        engine_version=engine_version,
        python_version=python_version,
        python_interpreter=service._resolve_python_interpreter(),
    )
    session.add(build)

    configuration.active_build_id = build.id
    configuration.active_build_fingerprint = fingerprint
    configuration.content_digest = digest
    await session.commit()

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
    )

    assert context.should_run is False
    assert build.status is BuildStatus.READY
    assert build.id == configuration.active_build_id
    assert context.fingerprint == fingerprint


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
                artifacts=BuildArtifacts(python_version="3.14.0", engine_version="0.2.0")
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
    assert refreshed.status is BuildStatus.READY
    assert refreshed.summary == "Build succeeded"
    console_messages = [
        evt.payload_dict().get("message")
        for evt in events
        if getattr(evt, "type", "") == "console.line"
    ]
    assert console_messages == ["log 1", "log 2"]
    assert any(getattr(evt, "type", "") == "build.completed" for evt in events)


@pytest.mark.asyncio()
async def test_ensure_local_env_uses_marker_when_ids_are_strings(
    session: AsyncSession,
    tmp_path: Path,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    builder = TrackingBuilder()
    service = service_factory(session, builder=builder)

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.READY,
        created_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
        fingerprint="fp-123",
        engine_spec="demo",
        engine_version="0.0.1",
        python_version="3.11.0",
    )
    session.add(build)
    await session.commit()

    venv_root = build_venv_root(
        service.settings, workspace.id, configuration.id, build.id
    )
    marker_path = venv_root / ".venv" / "ade_build.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_payload = {"build_id": str(build.id), "fingerprint": build.fingerprint}
    marker_path.write_text(json.dumps(marker_payload), encoding="utf-8")

    resolved = await service.ensure_local_env(build=build)

    assert resolved == marker_path.parent
    assert builder.invocations == 0
