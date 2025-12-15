import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ade_api.common.time import utc_now
from ade_api.db import Base
from ade_api.db.mixins import generate_uuid7
from ade_api.features.builds.builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    BuildStep,
)
from ade_api.features.builds.exceptions import BuildAlreadyInProgressError
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.features.builds.service import BuildDecision, BuildsService
from ade_api.features.configs.storage import ConfigStorage
from ade_api.features.runs.event_stream import RunEventStreamRegistry
from ade_api.infra.storage import build_venv_root
from ade_api.models import Build, BuildStatus, Configuration, ConfigurationStatus, Workspace
from ade_api.settings import Settings


@dataclass(slots=True)
class FakeBuilder:
    events: list[BuilderEvent]

    async def build(
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
    ) -> BuildArtifacts:
        artifacts: BuildArtifacts | None = None
        async for event in self.build_stream(
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
            if isinstance(event, BuilderArtifactsEvent):
                artifacts = event.artifacts

        assert artifacts is not None
        return artifacts

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
    [AsyncSession, FakeBuilder | None],
    BuildsService,
]:
    def _factory(
        session: AsyncSession,
        builder: FakeBuilder | None = None,
    ) -> BuildsService:
        base_settings = Settings()
        workspaces_dir = tmp_path / "workspaces"
        engine_dir = tmp_path / "engine"
        engine_dir.mkdir(parents=True, exist_ok=True)
        (engine_dir / "pyproject.toml").write_text(
            """
[project]
name = "ade-engine"
version = "1.6.1"
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
        storage = ConfigStorage(settings=settings)
        builder = builder or FakeBuilder(events=[])
        event_streams = RunEventStreamRegistry()
        return BuildsService(
            session=session,
            settings=settings,
            storage=storage,
            builder=builder,
            event_streams=event_streams,
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


async def _prepare_spec(service: BuildsService, workspace: Workspace, configuration: Configuration):
    config_path = service.storage.config_path(workspace.id, configuration.id)
    (config_path / "src" / "ade_config").mkdir(parents=True, exist_ok=True)
    (config_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.0.1'\n",
        encoding="utf-8",
    )
    return await service._build_spec(
        configuration=configuration,
        workspace_id=workspace.id,
    )


@pytest.mark.asyncio()
async def test_is_stale_handles_naive_datetimes(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))

    fixed_now = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    service._now = lambda: fixed_now  # type: ignore[assignment]

    timeout = service.settings.build_timeout

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.QUEUED,
        created_at=(fixed_now - timeout - timedelta(seconds=1)).replace(tzinfo=None),
    )
    assert service._is_stale(build) is True

    build.created_at = (fixed_now - timeout + timedelta(seconds=1)).replace(tzinfo=None)
    assert service._is_stale(build) is False

    build.started_at = (fixed_now - timeout - timedelta(seconds=1)).replace(tzinfo=None)
    assert service._is_stale(build) is True


@pytest.mark.asyncio()
async def test_prepare_build_reuses_ready_build(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))

    spec = await _prepare_spec(service, workspace, configuration)
    ready_build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.READY,
        created_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
        exit_code=0,
        fingerprint=spec.fingerprint,
        config_digest=spec.config_digest,
        engine_spec=spec.engine_spec,
        engine_version=spec.engine_version_hint,
        python_version=spec.python_version,
        python_interpreter=spec.python_bin,
    )
    session.add(ready_build)
    configuration.active_build_id = ready_build.id
    configuration.active_build_fingerprint = spec.fingerprint
    configuration.content_digest = spec.config_digest
    await session.commit()

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
    )

    assert context.decision is BuildDecision.REUSE_READY
    assert context.reuse_summary == "Reused existing build"
    assert build.status is BuildStatus.READY
    assert build.id == configuration.active_build_id
    assert context.fingerprint == spec.fingerprint


@pytest.mark.asyncio()
async def test_prepare_build_join_inflight_when_allowed(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await _prepare_spec(service, workspace, configuration)

    inflight = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.QUEUED,
        created_at=utc_now(),
        fingerprint=spec.fingerprint,
        config_digest=spec.config_digest,
        engine_spec=spec.engine_spec,
        engine_version=spec.engine_version_hint,
        python_version=spec.python_version,
        python_interpreter=spec.python_bin,
    )
    session.add(inflight)
    await session.commit()

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
        allow_inflight=True,
    )

    assert build.id == inflight.id
    assert context.decision is BuildDecision.START_NEW
    assert context.reuse_summary is None


@pytest.mark.asyncio()
async def test_prepare_build_blocks_matching_inflight_when_disallowed(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await _prepare_spec(service, workspace, configuration)

    inflight = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.BUILDING,
        created_at=utc_now(),
        fingerprint=spec.fingerprint,
        config_digest=spec.config_digest,
        engine_spec=spec.engine_spec,
        engine_version=spec.engine_version_hint,
        python_version=spec.python_version,
        python_interpreter=spec.python_bin,
    )
    session.add(inflight)
    await session.commit()

    with pytest.raises(BuildAlreadyInProgressError):
        await service.prepare_build(
            workspace_id=workspace.id,
            configuration_id=configuration.id,
            options=BuildCreateOptions(force=False, wait=False),
        )


@pytest.mark.asyncio()
async def test_prepare_build_returns_queued_inflight_when_wait_requested(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await _prepare_spec(service, workspace, configuration)

    inflight = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.QUEUED,
        created_at=utc_now(),
        fingerprint=spec.fingerprint,
        config_digest=spec.config_digest,
        engine_spec=spec.engine_spec,
        engine_version=spec.engine_version_hint,
        python_version=spec.python_version,
        python_interpreter=spec.python_bin,
    )
    session.add(inflight)
    await session.commit()

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=True),
    )

    assert build.id == inflight.id
    assert context.decision is BuildDecision.START_NEW


@pytest.mark.asyncio()
async def test_prepare_build_blocks_other_inflight_when_disallowed(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await _prepare_spec(service, workspace, configuration)

    other_inflight = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.BUILDING,
        created_at=utc_now(),
        fingerprint=f"{spec.fingerprint}-other",
        config_digest="other",
    )
    session.add(other_inflight)
    await session.commit()

    with pytest.raises(BuildAlreadyInProgressError):
        await service.prepare_build(
            workspace_id=workspace.id,
            configuration_id=configuration.id,
            options=BuildCreateOptions(force=False, wait=False),
        )


@pytest.mark.asyncio()
async def test_prepare_build_conflicting_inflight_can_be_joined_when_allowed(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await _prepare_spec(service, workspace, configuration)

    other_inflight = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.BUILDING,
        created_at=utc_now(),
        fingerprint=f"{spec.fingerprint}-other",
        config_digest="other",
    )
    session.add(other_inflight)
    await session.commit()

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
        allow_inflight=True,
    )

    assert build.id == other_inflight.id
    assert context.decision is BuildDecision.JOIN_INFLIGHT


@pytest.mark.asyncio()
async def test_prepare_build_force_rebuild_creates_new_row(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    builder = FakeBuilder(events=[])
    service = service_factory(session, builder=builder)

    spec = await _prepare_spec(service, workspace, configuration)
    existing = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.READY,
        created_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
        exit_code=0,
        fingerprint=spec.fingerprint,
        config_digest=spec.config_digest,
        engine_spec=spec.engine_spec,
        engine_version=spec.engine_version_hint,
        python_version=spec.python_version,
        python_interpreter=spec.python_bin,
    )
    session.add(existing)
    configuration.active_build_id = existing.id
    configuration.active_build_fingerprint = spec.fingerprint
    configuration.content_digest = spec.config_digest
    await session.commit()

    new_build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=True, wait=False),
    )

    total_builds = (await session.execute(select(func.count()).select_from(Build))).scalar_one()

    assert new_build.id != existing.id
    assert new_build.status is BuildStatus.QUEUED
    assert context.decision is BuildDecision.START_NEW
    assert total_builds == 2


@pytest.mark.asyncio()
async def test_stream_build_success(
    session: AsyncSession,
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
                artifacts=BuildArtifacts(python_version="3.14.0", engine_version="1.6.1")
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
        (evt.get("data") or {}).get("message")
        for evt in events
        if evt.get("event") == "console.line"
    ]
    assert console_messages == ["log 1", "log 2"]
    assert any(evt.get("event") == "build.complete" for evt in events)


@pytest.mark.asyncio()
async def test_stream_build_reuse_short_circuits_and_reports_summary(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    builder = TrackingBuilder()
    service = service_factory(session, builder=builder)
    spec = await _prepare_spec(service, workspace, configuration)

    ready = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.READY,
        created_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
        exit_code=0,
        fingerprint=spec.fingerprint,
        config_digest=spec.config_digest,
        engine_spec=spec.engine_spec,
        engine_version=spec.engine_version_hint,
        python_version=spec.python_version,
        python_interpreter=spec.python_bin,
    )
    session.add(ready)
    configuration.active_build_id = ready.id
    configuration.active_build_fingerprint = spec.fingerprint
    await session.commit()

    _, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
    )
    ready.summary = None
    await session.commit()

    events = [
        evt
        async for evt in service.stream_build(
            context=context,
            options=BuildCreateOptions(force=False, wait=False),
        )
    ]
    payloads = [evt.get("data") for evt in events if evt.get("event") == "build.complete"]
    assert payloads and payloads[-1].get("summary") == "Reused existing build"
    assert builder.invocations == 0


@pytest.mark.asyncio()
async def test_stream_build_join_replays_existing_and_live_events(
    session: AsyncSession,
    service_factory,
) -> None:
    workspace, configuration = await _create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await _prepare_spec(service, workspace, configuration)

    inflight = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.BUILDING,
        created_at=utc_now(),
        fingerprint=spec.fingerprint,
        config_digest=spec.config_digest,
        engine_spec=spec.engine_spec,
    )
    session.add(inflight)
    await session.commit()

    stream = service.event_log_reader(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        build_id=inflight.id,
    )
    await stream.append({
        "event": "build.queued",
        "payload": {"status": "queued"},
    })
    await stream.append({
        "event": "build.start",
        "payload": {"status": "building"},
    })

    _, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
        allow_inflight=True,
    )

    async def emit_live_events():
        await asyncio.sleep(0)
        await stream.append({
            "event": "console.line",
            "payload": {"message": "log", "stream": "stdout", "scope": "build"},
        })
        await stream.append({
            "event": "build.complete",
            "payload": {"status": "ready", "exit_code": 0},
        })

    producer = asyncio.create_task(emit_live_events())
    events = [
        evt
        async for evt in service.stream_build(
            context=context,
            options=BuildCreateOptions(force=False, wait=False),
        )
    ]
    await producer

    event_types = [evt.get("event") for evt in events]
    assert event_types[0] == "build.queued"
    assert "build.start" in event_types
    assert event_types[-1] == "build.complete"
    assert event_types.count("build.complete") == 1


@pytest.mark.asyncio()
async def test_ensure_local_env_uses_marker_when_ids_are_strings(
    session: AsyncSession,
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

    venv_root = build_venv_root(service.settings, workspace.id, configuration.id, build.id)
    marker_path = venv_root / ".venv" / "ade_build.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_payload = {
        "build_id": str(build.id),
        "fingerprint": build.fingerprint,
        "engine_version": build.engine_version,
    }
    marker_path.write_text(json.dumps(marker_payload), encoding="utf-8")

    resolved = await service.ensure_local_env(build=build)

    assert resolved == marker_path.parent
    assert builder.invocations == 0
