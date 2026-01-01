import pytest
from sqlalchemy import func, select

from ade_api.common.time import utc_now
from ade_api.common.ids import generate_uuid7
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.features.builds.service import BuildDecision
from ade_api.models import Build, BuildStatus

from tests.unit.features.builds.helpers import FakeBuilder, create_configuration, prepare_spec


@pytest.mark.asyncio()
async def test_prepare_build_reuses_ready_build(
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))

    spec = await prepare_spec(service, workspace, configuration)
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
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await prepare_spec(service, workspace, configuration)

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
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await prepare_spec(service, workspace, configuration)

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

    build, context = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
    )
    assert build.id == inflight.id
    assert context.decision is BuildDecision.JOIN_INFLIGHT


@pytest.mark.asyncio()
async def test_prepare_build_returns_queued_inflight_when_wait_requested(
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await prepare_spec(service, workspace, configuration)

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
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await prepare_spec(service, workspace, configuration)

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
    )
    assert build.id != other_inflight.id
    assert context.decision is BuildDecision.START_NEW


@pytest.mark.asyncio()
async def test_prepare_build_conflicting_inflight_can_be_joined_when_allowed(
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    service = service_factory(session, builder=FakeBuilder(events=[]))
    spec = await prepare_spec(service, workspace, configuration)

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

    assert build.id != other_inflight.id
    assert context.decision is BuildDecision.START_NEW


@pytest.mark.asyncio()
async def test_prepare_build_force_rebuild_creates_new_row(
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    builder = FakeBuilder(events=[])
    service = service_factory(session, builder=builder)

    spec = await prepare_spec(service, workspace, configuration)
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

    assert new_build.id == existing.id
    assert new_build.status is BuildStatus.QUEUED
    assert context.decision is BuildDecision.START_NEW
    assert total_builds == 1
