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
    log_path.write_text(
        "\n".join(json.dumps(evt) for evt in events) + "\n",
        encoding="utf-8",
    )

    messages = [
        msg
        async for msg in stream_ndjson_events(
            path=log_path,
            start_sequence=0,
            stop_events={"run.complete"},
            ping_interval=0.01,
        )
    ]

    assert len(messages) == 2
    assert messages[0]["id"] == "1"
    assert messages[0]["event"] == "run.queued"
    first_payload = json.loads(messages[0]["data"])
    assert first_payload["event"] == "run.queued"
    assert "sequence" not in first_payload

    assert messages[1]["id"] == "2"
    assert messages[1]["event"] == "run.complete"
    second_payload = json.loads(messages[1]["data"])
    assert second_payload["data"]["status"] == "succeeded"


async def test_stream_ndjson_events_resumes_after_sequence(tmp_path) -> None:
    log_path = tmp_path / "events.ndjson"
    events = [
        {"event": "run.queued", "sequence": 1, "data": {"status": "queued"}},
        {"event": "run.complete", "sequence": 2, "data": {"status": "succeeded"}},
    ]
    log_path.write_text(
        "\n".join(json.dumps(evt) for evt in events) + "\n",
        encoding="utf-8",
    )

    messages = [
        msg
        async for msg in stream_ndjson_events(
            path=log_path,
            start_sequence=1,
            stop_events={"run.complete"},
            ping_interval=0.01,
        )
    ]

    assert len(messages) == 1
    assert messages[0]["id"] == "2"
    assert messages[0]["event"] == "run.complete"
