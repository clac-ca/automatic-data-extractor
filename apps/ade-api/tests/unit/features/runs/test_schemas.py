from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ade_api.features.runs.schemas import (
    RunCreateOptions,
    RunCreateRequest,
    RunEventsPage,
    RunLinks,
    RunOutputFile,
    RunOutputListing,
    RunResource,
)


def _ts(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def test_run_resource_serialization_uses_aliases() -> None:
    run_id = str(uuid4())
    workspace_id = str(uuid4())
    configuration_id = str(uuid4())
    resource = RunResource(
        id=run_id,
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        status="queued",
        created_at=_ts(1_700_000_000),
        links=RunLinks(
            self=f"/api/v1/runs/{run_id}",
            summary=f"/api/v1/runs/{run_id}/summary",
            events=f"/api/v1/runs/{run_id}/events",
            events_stream=f"/api/v1/runs/{run_id}/events/stream",
            logs=f"/api/v1/runs/{run_id}/logs",
            outputs=f"/api/v1/runs/{run_id}/outputs",
        ),
    )

    payload = resource.model_dump()
    assert payload["object"] == "ade.run"
    assert payload["status"] == "queued"
    assert payload["input"]["document_ids"] == []
    assert payload["output"]["output_count"] == 0
    assert payload["links"]["summary"].endswith("/summary")
    assert "failure_message" not in payload


def test_run_create_request_defaults_include_options() -> None:
    request = RunCreateRequest()
    assert isinstance(request.options, RunCreateOptions)
    assert "stream" not in request.model_dump()


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
