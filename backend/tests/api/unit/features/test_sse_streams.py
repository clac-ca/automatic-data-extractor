from __future__ import annotations

import json

import pytest

from ade_api.common.sse import stream_ndjson_events

pytestmark = pytest.mark.asyncio


async def test_stream_ndjson_events_replays_and_stops(tmp_path) -> None:
    log_path = tmp_path / "events.ndjson"
    events = [
        {"event": "run.queued", "sequence": 1, "data": {"status": "queued"}},
        {"event": "run.complete", "sequence": 2, "data": {"status": "succeeded"}},
    ]
    offsets = []
    cursor = 0
    for event in events:
        raw = json.dumps(event).encode("utf-8")
        cursor += len(raw) + 1
        offsets.append(cursor)
    log_path.write_text(
        "\n".join(json.dumps(evt) for evt in events) + "\n",
        encoding="utf-8",
    )

    messages = [
        msg
        async for msg in stream_ndjson_events(
            path=log_path,
            start_offset=0,
            stop_events={"run.complete"},
            ping_interval=0.01,
        )
    ]

    assert len(messages) == 2
    assert messages[0]["id"] == str(offsets[0])
    assert messages[0]["event"] == "run.queued"
    first_payload = json.loads(messages[0]["data"])
    assert first_payload["event"] == "run.queued"
    assert first_payload["sequence"] == 1

    assert messages[1]["id"] == str(offsets[1])
    assert messages[1]["event"] == "run.complete"
    second_payload = json.loads(messages[1]["data"])
    assert second_payload["data"]["status"] == "succeeded"


async def test_stream_ndjson_events_resumes_after_offset(tmp_path) -> None:
    log_path = tmp_path / "events.ndjson"
    events = [
        {"event": "run.queued", "sequence": 1, "data": {"status": "queued"}},
        {"event": "run.complete", "sequence": 2, "data": {"status": "succeeded"}},
    ]
    raw_lines = [json.dumps(evt) for evt in events]
    first_offset = len(raw_lines[0].encode("utf-8")) + 1
    second_offset = first_offset + len(raw_lines[1].encode("utf-8")) + 1
    log_path.write_text(
        "\n".join(raw_lines) + "\n",
        encoding="utf-8",
    )

    messages = [
        msg
        async for msg in stream_ndjson_events(
            path=log_path,
            start_offset=first_offset,
            stop_events={"run.complete"},
            ping_interval=0.01,
        )
    ]

    assert len(messages) == 1
    assert messages[0]["id"] == str(second_offset)
    assert messages[0]["event"] == "run.complete"
