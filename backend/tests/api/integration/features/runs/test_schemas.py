from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ade_api.features.runs.schemas import (
    RunCreateOptions,
    RunCreateRequest,
    RunLinks,
    RunResource,
)
from ade_db.models import RunOperation, RunStatus


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
        operation=RunOperation.PROCESS,
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
    request = RunCreateRequest(
        options=RunCreateOptions(input_document_id=uuid4()),
    )
    payload = request.model_dump()

    assert payload == {
        "options": {
            "operation": "process",
            "dry_run": False,
            "active_sheet_only": False,
            "input_document_id": request.options.input_document_id,
        }
    }
