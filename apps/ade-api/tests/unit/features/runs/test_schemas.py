from __future__ import annotations

from datetime import datetime, timezone

from ade_api.features.runs.schemas import (
    RunCreateOptions,
    RunCreateRequest,
    RunEventsPage,
    RunLinks,
    RunLogsResponse,
    RunOutputFile,
    RunOutputListing,
    RunResource,
)


def _ts(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def test_run_resource_serialization_uses_aliases() -> None:
    resource = RunResource(
        id="run_123",
        workspace_id="ws_1",
        configuration_id="cfg_456",
        status="queued",
        created_at=_ts(1_700_000_000),
        links=RunLinks(
            self="/api/v1/runs/run_123",
            summary="/api/v1/runs/run_123/summary",
            events="/api/v1/runs/run_123/events",
            logs="/api/v1/runs/run_123/logs",
            logfile="/api/v1/runs/run_123/logfile",
            outputs="/api/v1/runs/run_123/outputs",
            diagnostics="/api/v1/runs/run_123/diagnostics",
        ),
    )

    payload = resource.model_dump()
    assert payload["object"] == "ade.run"
    assert payload["status"] == "queued"
    assert payload["input"]["document_ids"] == []
    assert payload["output"]["output_count"] == 0
    assert payload["links"]["summary"].endswith("/summary")
    assert "failure_message" not in payload


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


def test_run_events_page_serializes_cursor() -> None:
    page = RunEventsPage(items=[], next_after_sequence=9)
    payload = page.model_dump()
    assert payload["next_after_sequence"] == 9


def test_run_output_listing_shapes_entries() -> None:
    listing = RunOutputListing(
        files=[
            RunOutputFile(
                name="normalized.xlsx",
                kind="normalized_workbook",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                byte_size=512,
                download_url="/api/v1/runs/run_123/outputs/normalized.xlsx",
            )
        ]
    )
    payload = listing.model_dump()
    assert payload["files"][0]["name"] == "normalized.xlsx"
    assert payload["files"][0]["download_url"].endswith("normalized.xlsx")
