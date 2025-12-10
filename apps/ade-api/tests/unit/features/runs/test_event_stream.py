import asyncio
import json
from pathlib import Path

import pytest

from ade_api.features.runs.event_stream import RunEventContext, RunEventStream
from ade_api.schemas.event_record import new_event_record

pytestmark = pytest.mark.asyncio()


def _stream(tmp_path: Path) -> RunEventStream:
    path = tmp_path / "events.ndjson"
    context = RunEventContext(
        job_id="job",
        workspace_id="workspace",
        build_id=None,
        configuration_id="config",
    )
    return RunEventStream(path=path, context=context)


async def test_append_assigns_sequence_and_persists(tmp_path: Path) -> None:
    stream = _stream(tmp_path)
    event = await stream.append(new_event_record(event="run.queued", data={"status": "queued"}))

    saved = (tmp_path / "events.ndjson").read_text(encoding="utf-8").strip().splitlines()
    assert len(saved) == 1

    parsed = json.loads(saved[0])
    assert parsed["event"] == "run.queued"


async def test_sequences_resume_from_disk(tmp_path: Path) -> None:
    stream = _stream(tmp_path)
    await stream.append(new_event_record(event="run.queued"))
    await stream.append(new_event_record(event="run.start"))

    resumed = _stream(tmp_path)
    next_event = await resumed.append(new_event_record(event="run.phase", data={"phase": "x"}))

    assert next_event["event"] == "run.phase"


async def test_subscribers_receive_events(tmp_path: Path) -> None:
    stream = _stream(tmp_path)
    async with stream.subscribe() as subscription:
        emitted = await stream.append(new_event_record(event="run.queued"))
        received = await asyncio.wait_for(subscription.__anext__(), timeout=1)

    assert received["event_id"] == emitted["event_id"]


async def test_iter_filters_by_sequence(tmp_path: Path) -> None:
    stream = _stream(tmp_path)
    await stream.append(new_event_record(event="run.queued"))
    await stream.append(new_event_record(event="run.start"))

    events = list(stream.iter_persisted(after_sequence=1))
    assert len(events) == 1
    assert events[0]["event"] == "run.start"
