from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request

from ade_api.common.events import EventRecord, new_event_record
from ade_api.features.builds.router import stream_build_events_endpoint
from ade_api.features.runs.router import stream_run_events_endpoint
from ade_api.models import BuildStatus, RunStatus

pytestmark = pytest.mark.asyncio


class _ListReader:
    def __init__(self, events: list[EventRecord]) -> None:
        self._events = events

    def iter_persisted(self, *, after_sequence: int | None = None):
        for event in self._events:
            seq = event.get("sequence")
            if after_sequence is not None and isinstance(seq, int):
                if seq <= after_sequence:
                    continue
            yield event


class _EmptySubscription:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _StubBuildsService:
    def __init__(self, *, build_id, workspace_id, configuration_id, events: list[EventRecord]):
        self._build = SimpleNamespace(
            id=build_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            status=BuildStatus.READY,
        )
        self._events = events

    async def get_build(self, build_id):
        if build_id == self._build.id:
            return self._build
        return None

    async def launch_build_if_needed(self, *, build, reason, run_id):  # noqa: ANN001,ARG002
        return None

    def event_log_reader(self, *, workspace_id, configuration_id, build_id):
        return _ListReader(self._events)

    def iter_events(self, *, build, after_sequence: int | None = None):  # noqa: ANN001
        return _ListReader(self._events).iter_persisted(after_sequence=after_sequence)

    @asynccontextmanager
    async def subscribe_to_events(self, build):
        yield _EmptySubscription()


class _StubRunsService:
    def __init__(self, *, run_id, workspace_id, configuration_id, events: list[EventRecord]):
        self._run = SimpleNamespace(
            id=run_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            status=RunStatus.SUCCEEDED,
        )
        self._events = events

    async def get_run(self, run_id):
        if run_id == self._run.id:
            return self._run
        return None

    def iter_events(self, *, run, after_sequence: int | None = None):
        return _ListReader(self._events).iter_persisted(after_sequence=after_sequence)

    @asynccontextmanager
    async def subscribe_to_events(self, run):
        yield _EmptySubscription()


async def test_build_stream_formats_replayed_events_without_hanging() -> None:
    build_id = uuid4()
    workspace_id = uuid4()
    configuration_id = uuid4()
    events = [
        {**new_event_record(event="build.queued", data={"status": "queued"}), "sequence": 1},
        {
            **new_event_record(event="build.complete", data={"status": "ready", "exit_code": 0}),
            "sequence": 2,
        },
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
        {**new_event_record(event="run.queued", data={"status": "queued"}), "sequence": 1},
        {**new_event_record(event="run.complete", data={"status": "succeeded"}), "sequence": 2},
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

    assert len(payload) == 1  # resumed at id 1, so only the second event should stream
    lines = payload[0].splitlines()
    assert lines[0] == "id: 2"
    assert lines[1] == "event: run.complete"
    assert lines[2].startswith("data: ")
    data_obj = json.loads(lines[2].removeprefix("data: "))
    assert data_obj["data"]["status"] == "succeeded"
