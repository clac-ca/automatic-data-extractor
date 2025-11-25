from __future__ import annotations

import json

from ade_api.features.runs.schemas import (
    RunCompletedEvent,
    RunCreateOptions,
    RunCreateRequest,
    RunLogEvent,
    RunLogsResponse,
    RunResource,
)


def test_run_resource_serialization_uses_aliases() -> None:
    resource = RunResource(
        id="run_123",
        config_id="cfg_456",
        status="queued",
        created=1_700_000_000,
        started=None,
        finished=None,
        exit_code=None,
    )

    payload = resource.model_dump()
    assert payload["object"] == "ade.run"
    assert payload["attempt"] == 1
    assert payload["input_documents"] == []
    assert payload["output_paths"] == []
    assert payload["processed_files"] == []
    assert "config_version_id" not in payload
    assert "submitted_by_user_id" not in payload
    assert "retry_of_run_id" not in payload
    assert "trace_id" not in payload
    assert "canceled" not in payload
    assert "artifact_uri" not in payload
    assert "output_uri" not in payload
    assert "logs_uri" not in payload
    assert "artifact_path" not in payload
    assert "events_path" not in payload
    assert "summary" not in payload
    assert payload["status"] == "queued"


def test_run_log_event_json_bytes_round_trip() -> None:
    event = RunLogEvent(
        run_id="run_123",
        created=1_700_000_100,
        type="run.log",
        stream="stderr",
        message="line",
    )

    decoded = json.loads(event.json_bytes())
    assert decoded == {
        "object": "ade.run.event",
        "run_id": "run_123",
        "created": 1_700_000_100,
        "type": "run.log",
        "stream": "stderr",
        "message": "line",
    }


def test_run_logs_response_tracks_pagination_marker() -> None:
    response = RunLogsResponse(
        run_id="run_123",
        entries=[],
        next_after_id=42,
    )

    payload = response.model_dump()
    assert payload["object"] == "ade.run.logs"
    assert payload["next_after_id"] == 42


def test_run_create_request_defaults_to_no_stream() -> None:
    request = RunCreateRequest()
    assert request.stream is False
    assert isinstance(request.options, RunCreateOptions)


def test_run_completed_event_supports_optional_fields() -> None:
    event = RunCompletedEvent(
        run_id="run_123",
        created=1,
        status="succeeded",
        exit_code=0,
        error_message=None,
    )

    payload = event.model_dump()
    assert payload["status"] == "succeeded"
    assert payload["output_paths"] == []
    assert "artifact_path" not in payload
    assert "error_message" not in payload
