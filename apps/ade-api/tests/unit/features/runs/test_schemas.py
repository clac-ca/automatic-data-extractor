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
        output=f"/api/v1/runs/{run_str}/output",
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
    assert payload["input"]["document_id"] is None
    assert payload["input"]["input_sheet_name"] is None
    assert payload["output"]["has_output"] is False
    assert payload["output"]["output_path"] is None
    assert payload["output"]["processed_file"] is None
    assert payload["links"]["self"].endswith(str(run_identifiers["run_id"]))
    assert {"failure_code", "failure_stage", "failure_message"}.isdisjoint(payload)


def test_run_create_options_captures_input_document() -> None:
    primary = uuid4()
    options = RunCreateOptions(input_document_id=primary, input_sheet_name="Sheet1")

    assert options.input_document_id == primary
    assert options.input_sheet_name == "Sheet1"
    assert options.metadata is None


def test_run_create_request_serializes_minimal_options() -> None:
    request = RunCreateRequest()
    payload = request.model_dump()

    assert payload == {
        "options": {
            "dry_run": False,
            "validate_only": False,
            "force_rebuild": False,
            "input_document_id": None,
            "input_sheet_name": None,
            "metadata": None,
        }
    }


@pytest.mark.parametrize("cursor", [9, None])
def test_run_events_page_serialization_handles_cursor(cursor: int | None) -> None:
    payload = RunEventsPage(items=[], next_after_sequence=cursor).model_dump()

    assert ("next_after_sequence" in payload) is (cursor is not None)
    if cursor is not None:
        assert payload["next_after_sequence"] == cursor
