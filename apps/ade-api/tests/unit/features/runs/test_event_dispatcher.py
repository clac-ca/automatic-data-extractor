import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from ade_engine.schemas import AdeEvent

from ade_api.features.runs.event_dispatcher import (
    RunEventDispatcher,
    RunEventLogReader,
    RunEventStorage,
)
from ade_api.settings import Settings
from ade_api.common.time import utc_now


pytestmark = pytest.mark.asyncio()


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    workspaces = tmp_path / "workspaces"
    return Settings(
        workspaces_dir=workspaces,
        configs_dir=workspaces,
        documents_dir=workspaces,
        runs_dir=workspaces,
    )


@pytest.fixture()
def storage(settings: Settings) -> RunEventStorage:
    return RunEventStorage(settings=settings)


@pytest.fixture()
def dispatcher(storage: RunEventStorage) -> RunEventDispatcher:
    return RunEventDispatcher(storage=storage)


async def test_emit_assigns_event_id_and_sequence(
    dispatcher: RunEventDispatcher, settings: Settings
) -> None:
    workspace_id = uuid4()
    configuration_id = uuid4()
    run_id = uuid4()
    event = await dispatcher.emit(
        type="run.queued",
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        run_id=run_id,
        payload={"status": "queued", "mode": "execute", "options": {}},
    )

    assert event.event_id is not None
    assert event.event_id.startswith("evt_")
    assert event.sequence == 1

    path = RunEventStorage(settings=settings).events_path(
        workspace_id=workspace_id, run_id=run_id
    )
    saved = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(saved) == 1

    parsed = AdeEvent.model_validate_json(saved[0])
    assert parsed.sequence == 1
    assert parsed.event_id == event.event_id


async def test_sequences_increment_per_run(dispatcher: RunEventDispatcher) -> None:
    workspace_a = uuid4()
    configuration_a = uuid4()
    workspace_b = uuid4()
    configuration_b = uuid4()
    run_a = uuid4()
    run_b = uuid4()
    first = await dispatcher.emit(
        type="run.queued",
        workspace_id=workspace_a,
        configuration_id=configuration_a,
        run_id=run_a,
        payload={"status": "queued", "mode": "execute", "options": {}},
    )
    second = await dispatcher.emit(
        type="run.started",
        workspace_id=workspace_a,
        configuration_id=configuration_a,
        run_id=run_a,
        payload={"status": "in_progress", "mode": "execute"},
    )
    other_run = await dispatcher.emit(
        type="run.queued",
        workspace_id=workspace_b,
        configuration_id=configuration_b,
        run_id=run_b,
        payload={"status": "queued", "mode": "execute", "options": {}},
    )

    assert (first.sequence, second.sequence) == (1, 2)
    assert other_run.sequence == 1


async def test_sequences_resume_from_disk(
    storage: RunEventStorage, dispatcher: RunEventDispatcher
) -> None:
    workspace_id = uuid4()
    configuration_id = uuid4()
    run_id = uuid4()
    existing = AdeEvent(
        type="run.queued",
        event_id="evt_existing",
        created_at=utc_now(),
        sequence=3,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        run_id=run_id,
        payload={"status": "queued", "mode": "execute", "options": {}},
    )
    await storage.append(existing)

    resumed = await dispatcher.emit(
        type="run.started",
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        run_id=run_id,
        payload={"status": "in_progress", "mode": "execute"},
    )

    assert resumed.sequence == 4


async def test_subscribers_receive_events(dispatcher: RunEventDispatcher) -> None:
    workspace_id = uuid4()
    configuration_id = uuid4()
    run_id = uuid4()
    async with dispatcher.subscribe(run_id) as subscription:
        emitted = await dispatcher.emit(
            type="run.queued",
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            run_id=run_id,
            payload={"status": "queued", "mode": "execute", "options": {}},
        )

        received = await asyncio.wait_for(subscription.__anext__(), timeout=1)

    assert received.event_id == emitted.event_id
    assert received.sequence == emitted.sequence


async def test_log_reader_filters_by_sequence(storage: RunEventStorage) -> None:
    workspace_id = uuid4()
    run_id = uuid4()
    await storage.append(
        AdeEvent(
            type="run.queued",
            event_id="evt_first",
            created_at=utc_now(),
            sequence=1,
            workspace_id=workspace_id,
            configuration_id=uuid4(),
            run_id=run_id,
            payload={"status": "queued", "mode": "execute", "options": {}},
        )
    )
    await storage.append(
        AdeEvent(
            type="run.started",
            event_id="evt_second",
            created_at=utc_now(),
            sequence=2,
            workspace_id=workspace_id,
            configuration_id=uuid4(),
            run_id=run_id,
            payload={"status": "in_progress", "mode": "execute"},
        )
    )

    reader = RunEventLogReader(
        storage=storage, workspace_id=workspace_id, run_id=run_id
    )

    events = list(reader.iter(after_sequence=1))
    assert len(events) == 1
    assert events[0].sequence == 2
