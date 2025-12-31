import asyncio

import pytest

from ade_api.common.time import utc_now
from ade_api.db.mixins import generate_uuid7
from ade_api.features.builds.builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    BuildStep,
)
from ade_api.features.builds.schemas import BuildCreateOptions
from ade_api.models import Build, BuildStatus

from tests.unit.features.builds.helpers import FakeBuilder, TrackingBuilder, create_configuration, prepare_spec


@pytest.mark.asyncio()
async def test_stream_build_success(
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    builder = FakeBuilder(
        events=[
            BuilderStepEvent(step=BuildStep.CREATE_VENV, message="venv"),
            BuilderLogEvent(message="log 1"),
            BuilderStepEvent(step=BuildStep.INSTALL_ENGINE, message="install"),
            BuilderLogEvent(message="log 2"),
            BuilderArtifactsEvent(
                artifacts=BuildArtifacts(python_version="3.11.0", engine_version="1.6.1")
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
    session,
    service_factory,
) -> None:
    workspace, configuration = await create_configuration(session)
    builder = TrackingBuilder()
    service = service_factory(session, builder=builder)
    spec = await prepare_spec(service, workspace, configuration)

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
