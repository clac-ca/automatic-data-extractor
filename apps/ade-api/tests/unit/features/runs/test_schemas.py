from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ade_api.features.runs.schemas import (
    RunCreateOptions,
    RunCreateRequest,
    RunEventsPage,
    RunLinks,
    RunResource,
)
from ade_api.models import RunStatus


@pytest.fixture
def run_identifiers() -> dict[str, UUID]:
    return {
        "run_id": uuid4(),
        "workspace_id": uuid4(),
        "configuration_id": uuid4(),
    }


@pytest.fixture
def timestamp() -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC)


def _links_for(run_id: UUID) -> RunLinks:
    run_str = str(run_id)
    base = f"/api/v1/runs/{run_str}"
    return RunLinks(
        self=base,
        events=f"{base}/events",
        events_stream=f"{base}/events/stream",
        events_download=f"{base}/events/download",
        logs=f"{base}/events/download",
        input=f"{base}/input",
        input_download=f"{base}/input/download",
        output=f"{base}/output/download",
        output_download=f"{base}/output/download",
        output_metadata=f"{base}/output",
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
    assert payload["input"] == {}
    assert payload["output"] == {"ready": False, "has_output": False}
    assert payload["links"]["self"].endswith(str(run_identifiers["run_id"]))
    assert {"failure_code", "failure_stage", "failure_message"}.isdisjoint(payload)


def test_run_create_options_captures_input_document() -> None:
    primary = uuid4()
    options = RunCreateOptions(input_document_id=primary, input_sheet_names=["Sheet1"])

    assert options.input_document_id == primary
    assert options.input_sheet_names == ["Sheet1"]
    assert options.metadata is None


def test_run_create_request_serializes_minimal_options() -> None:
    request = RunCreateRequest()
    payload = request.model_dump()

    assert payload == {
        "options": {
            "dry_run": False,
            "validate_only": False,
            "force_rebuild": False,
            "debug": False,
        }
    }


@pytest.mark.parametrize("cursor", [9, None])
def test_run_events_page_serialization_handles_cursor(cursor: int | None) -> None:
    payload = RunEventsPage(items=[], next_after_sequence=cursor).model_dump()

    assert ("next_after_sequence" in payload) is (cursor is not None)
    if cursor is not None:
        assert payload["next_after_sequence"] == cursor
