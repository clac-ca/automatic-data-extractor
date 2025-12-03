from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from ade_api.core.models import RunStatus
from ade_api.features.runs.schemas import (
    RunCreateOptions,
    RunCreateRequest,
    RunEventsPage,
    RunLinks,
    RunOutputFile,
    RunOutputListing,
    RunResource,
)


@pytest.fixture
def run_identifiers() -> dict[str, UUID]:
    return {
        "run_id": uuid4(),
        "workspace_id": uuid4(),
        "configuration_id": uuid4(),
    }


@pytest.fixture
def timestamp() -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def _links_for(run_id: UUID) -> RunLinks:
    run_str = str(run_id)
    return RunLinks(
        self=f"/api/v1/runs/{run_str}",
        summary=f"/api/v1/runs/{run_str}/summary",
        events=f"/api/v1/runs/{run_str}/events",
        events_stream=f"/api/v1/runs/{run_str}/events/stream",
        logs=f"/api/v1/runs/{run_str}/logs",
        outputs=f"/api/v1/runs/{run_str}/outputs",
    )


def test_run_resource_dump_uses_aliases_and_defaults(
    run_identifiers: dict[str, UUID], timestamp: datetime
) -> None:
    resource = RunResource(
        id=run_identifiers["run_id"],
        workspace_id=run_identifiers["workspace_id"],
        configuration_id=run_identifiers["configuration_id"],
        status=RunStatus.QUEUED,
        created_at=timestamp,
        links=_links_for(run_identifiers["run_id"]),
    )

    payload = resource.model_dump()

    assert payload["object"] == "ade.run"
    assert payload["status"] == RunStatus.QUEUED.value
    assert payload["input"] == {"document_ids": [], "input_sheet_names": []}
    assert payload["output"] == {
        "has_outputs": False,
        "output_count": 0,
        "processed_files": [],
    }
    assert payload["links"]["self"].endswith(str(run_identifiers["run_id"]))
    assert {"failure_code", "failure_stage", "failure_message"}.isdisjoint(payload)


def test_run_create_options_normalizes_document_references() -> None:
    primary = uuid4()
    secondary = uuid4()

    cases = [
        ({"document_ids": [primary]}, [primary], primary),
        ({"input_document_id": primary}, [primary], primary),
        (
            {"document_ids": [primary, secondary], "input_document_id": secondary},
            [primary, secondary],
            secondary,
        ),
    ]

    for options_kwargs, expected_ids, expected_primary in cases:
        options = RunCreateOptions(**options_kwargs)
        assert options.document_ids == expected_ids
        assert options.input_document_id == expected_primary


def test_run_create_request_serializes_minimal_options() -> None:
    request = RunCreateRequest()
    payload = request.model_dump()

    assert payload == {
        "options": {
            "dry_run": False,
            "validate_only": False,
            "force_rebuild": False,
        }
    }


@pytest.mark.parametrize("cursor", [9, None])
def test_run_events_page_serialization_handles_cursor(cursor: int | None) -> None:
    payload = RunEventsPage(items=[], next_after_sequence=cursor).model_dump()

    assert ("next_after_sequence" in payload) is (cursor is not None)
    if cursor is not None:
        assert payload["next_after_sequence"] == cursor


def test_run_output_listing_serializes_files_and_strips_empty_fields() -> None:
    listing = RunOutputListing(
        files=[
            RunOutputFile(
                name="normalized.xlsx",
                kind="normalized_workbook",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                byte_size=512,
                download_url="/api/v1/runs/run_123/outputs/normalized.xlsx",
            ),
            RunOutputFile(
                name="raw.csv",
                byte_size=128,
            ),
        ]
    )

    payload = listing.model_dump()
    first, second = payload["files"]

    assert first["kind"] == "normalized_workbook"
    assert first["download_url"].endswith("normalized.xlsx")
    assert first["byte_size"] == 512

    assert second["name"] == "raw.csv"
    assert second["byte_size"] == 128
    assert "download_url" not in second
    assert "kind" not in second
    assert "content_type" not in second
