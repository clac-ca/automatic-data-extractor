from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request

from ade_api.features.builds.router import stream_build_events_endpoint
from ade_api.features.runs.router import stream_run_events_endpoint
from ade_engine.schemas import AdeEvent

pytestmark = pytest.mark.asyncio


class _ListReader:
    def __init__(self, events: list[AdeEvent]) -> None:
        self._events = events

    def iter(self, *, after_sequence: int | None = None):
        for event in self._events:
            if after_sequence is not None and event.sequence is not None:
                if event.sequence <= after_sequence:
                    continue
            yield event


class _EmptySubscription:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _StubBuildsService:
    def __init__(self, *, build_id, workspace_id, configuration_id, events: list[AdeEvent]):
        self._build = SimpleNamespace(
            id=build_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        self._events = events

    async def get_build(self, build_id):
        if build_id == self._build.id:
            return self._build
        return None

    def event_log_reader(self, *, workspace_id, configuration_id, build_id):
        return _ListReader(self._events)

    @asynccontextmanager
    async def subscribe_to_events(self, build_id):
        yield _EmptySubscription()


class _StubRunsService:
    def __init__(self, *, run_id, workspace_id, configuration_id, events: list[AdeEvent]):
        self._run = SimpleNamespace(
            id=run_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        )
        self._events = events

    async def get_run(self, run_id):
        if run_id == self._run.id:
            return self._run
        return None

    def event_log_reader(self, *, workspace_id, run_id):
        return _ListReader(self._events)

    @asynccontextmanager
    async def subscribe_to_events(self, run_id):
        yield _EmptySubscription()


async def test_build_stream_formats_replayed_events_without_hanging() -> None:
    build_id = uuid4()
    workspace_id = uuid4()
    configuration_id = uuid4()
    events = [
        AdeEvent(
            type="build.queued",
            event_id="evt_build_1",
            created_at=datetime.utcnow(),
            sequence=1,
            source="api",
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
            payload={"status": "queued"},
        ),
        AdeEvent(
            type="build.complete",
            event_id="evt_build_2",
            created_at=datetime.utcnow(),
            sequence=2,
            source="api",
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
            payload={"status": "ready", "exit_code": 0},
        ),
    ]

    service = _StubBuildsService(
        build_id=build_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        events=events,
    )
    request = Request({"type": "http", "headers": []})
    response = await stream_build_events_endpoint(
        build_id,
        request,
        after_sequence=0,
        service=service,
    )

    chunks = [chunk async for chunk in response.body_iterator]
    payload = b"".join(chunks).decode("utf-8").strip().split("\n\n")

    assert len(payload) == 2
    first_lines = payload[0].splitlines()
    assert first_lines[0] == "id: 1"
    assert first_lines[1] == "event: build.queued"
    assert first_lines[2].startswith("data: ")
    assert "build.complete" in payload[1]
    assert "exit_code" in payload[1]


async def test_run_stream_respects_resume_cursor_header() -> None:
    run_id = uuid4()
    workspace_id = uuid4()
    configuration_id = uuid4()
    events = [
        AdeEvent(
            type="run.queued",
            event_id="evt_run_1",
            created_at=datetime.utcnow(),
            sequence=1,
            source="api",
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            run_id=run_id,
            payload={"status": "queued"},
        ),
        AdeEvent(
            type="run.complete",
            event_id="evt_run_2",
            created_at=datetime.utcnow(),
            sequence=2,
            source="api",
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            run_id=run_id,
            payload={"status": "succeeded"},
        ),
    ]

    service = _StubRunsService(
        run_id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        events=events,
    )
    request = Request({"type": "http", "headers": [(b"last-event-id", b"1")]})
    response = await stream_run_events_endpoint(
        run_id,
        request,
        after_sequence=None,
        service=service,
    )

    chunks = [chunk async for chunk in response.body_iterator]
    payload = b"".join(chunks).decode("utf-8").strip().split("\n\n")

    assert len(payload) == 1  # resumed at sequence 1, so only the second event should stream
    lines = payload[0].splitlines()
    assert lines[0] == "id: 2"
    assert lines[1] == "event: run.complete"
    assert lines[2].startswith("data: ")
    assert '"status":"succeeded"' in payload[0]
