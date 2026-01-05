import pytest

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.models import Build, BuildStatus

from tests.unit.features.builds.helpers import create_configuration, ensure_config_package


@pytest.mark.asyncio()
async def test_prepare_build_reuses_ready_build(
    session,
    service,
    storage,
) -> None:
    workspace, configuration = await create_configuration(session)
    ensure_config_package(storage, workspace_id=workspace.id, configuration_id=configuration.id)
    spec = await service._build_spec(
        configuration=configuration,
        workspace_id=workspace.id,
    )

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
        python_version=None,
        python_interpreter=None,
    )
    session.add(ready_build)
    configuration.active_build_id = ready_build.id
    configuration.active_build_fingerprint = spec.fingerprint
    configuration.content_digest = spec.config_digest
    await session.commit()

    build = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
    )

    assert build.id == ready_build.id
    assert build.status is BuildStatus.READY
    assert configuration.active_build_fingerprint == spec.fingerprint


@pytest.mark.asyncio()
async def test_prepare_build_creates_queued_build_when_none_exists(
    session,
    service,
    storage,
) -> None:
    workspace, configuration = await create_configuration(session)
    ensure_config_package(storage, workspace_id=workspace.id, configuration_id=configuration.id)

    build = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
    )

    assert build.status is BuildStatus.QUEUED
    assert build.workspace_id == workspace.id
    assert build.configuration_id == configuration.id


@pytest.mark.asyncio()
async def test_prepare_build_force_resets_ready_build(
    session,
    service,
    storage,
) -> None:
    workspace, configuration = await create_configuration(session)
    ensure_config_package(storage, workspace_id=workspace.id, configuration_id=configuration.id)
    spec = await service._build_spec(
        configuration=configuration,
        workspace_id=workspace.id,
    )

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
        python_version=None,
        python_interpreter=None,
    )
    session.add(ready_build)
    configuration.active_build_id = ready_build.id
    configuration.active_build_fingerprint = spec.fingerprint
    configuration.content_digest = spec.config_digest
    await session.commit()

    build = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=True, wait=False),
    )

    assert build.id == ready_build.id
    assert build.status is BuildStatus.QUEUED
    assert build.exit_code is None


@pytest.mark.asyncio()
async def test_prepare_build_resets_failed_build(
    session,
    service,
    storage,
) -> None:
    workspace, configuration = await create_configuration(session)
    ensure_config_package(storage, workspace_id=workspace.id, configuration_id=configuration.id)
    spec = await service._build_spec(
        configuration=configuration,
        workspace_id=workspace.id,
    )

    failed_build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.FAILED,
        created_at=utc_now(),
        fingerprint=spec.fingerprint,
        config_digest=spec.config_digest,
        engine_spec=spec.engine_spec,
    )
    session.add(failed_build)
    await session.commit()

    build = await service.prepare_build(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        options=BuildCreateOptions(force=False, wait=False),
    )

    assert build.id == failed_build.id
    assert build.status is BuildStatus.QUEUED
