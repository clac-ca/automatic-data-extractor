"""Tests for the job API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import re

from backend.app.db import get_sessionmaker
from backend.app.services.events import EventRecord, record_event


def _activate_configuration(
    client, *, document_type: str = "remittance", title: str = "Active configuration"
) -> dict[str, Any]:
    payload = {
        "document_type": document_type,
        "title": title,
        "payload": {"rules": []},
        "is_active": True,
    }
    response = client.post("/configurations", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_job_payload(document_type: str = "remittance") -> dict[str, Any]:
    return {
        "document_type": document_type,
        "created_by": "jkropp",
        "status": "running",
        "input": {
            "uri": "var/documents/remit_2025-09.pdf",
            "hash": "sha256:a93c...ff12",
            "expires_at": "2025-10-01T00:00:00Z",
        },
        "outputs": {
            "json": {
                "uri": "var/outputs/remit_2025-09.json",
                "expires_at": "2026-01-01T00:00:00Z",
            }
        },
        "metrics": {
            "rows_extracted": 125,
            "processing_time_ms": 4180,
            "errors": 0,
        },
        "logs": [
            {
                "ts": "2025-09-17T18:42:00Z",
                "level": "info",
                "message": "Job started",
            }
        ],
    }


def _job_sequence(job_id: str) -> int:
    return int(job_id.rsplit("_", 1)[-1])


def test_create_job_uses_active_configuration(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    payload = _create_job_payload(configuration["document_type"])
    response = client.post("/jobs", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert re.fullmatch(r"job_\d{4}_\d{2}_\d{2}_\d{4}", data["job_id"])
    assert data["document_type"] == payload["document_type"]
    assert data["configuration_version"] == configuration["version"]
    assert data["status"] == payload["status"]
    assert data["created_by"] == payload["created_by"]
    assert data["input"] == payload["input"]
    assert data["outputs"] == payload["outputs"]
    assert data["metrics"] == payload["metrics"]
    assert data["logs"] == payload["logs"]
    datetime.fromisoformat(data["created_at"])
    datetime.fromisoformat(data["updated_at"])


def test_create_job_with_explicit_configuration(app_client) -> None:
    client, _, _ = app_client
    active = _activate_configuration(client, title="Draft to activate")
    draft_payload = {
        "document_type": active["document_type"],
        "title": "Historical version",
        "payload": {"rules": ["legacy"]},
    }
    draft_response = client.post("/configurations", json=draft_payload)
    assert draft_response.status_code == 201
    draft_configuration = draft_response.json()

    payload = _create_job_payload(active["document_type"])
    payload["configuration_id"] = draft_configuration["configuration_id"]
    payload["status"] = "pending"

    response = client.post("/jobs", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["configuration_version"] == draft_configuration["version"]
    assert data["status"] == "pending"


def test_create_job_rejects_configuration_for_other_document_type(app_client) -> None:
    client, _, _ = app_client
    invoice_configuration = _activate_configuration(client, document_type="invoice")
    remittance_configuration = _activate_configuration(client, document_type="remittance")

    payload = _create_job_payload(remittance_configuration["document_type"])
    payload["configuration_id"] = invoice_configuration["configuration_id"]

    response = client.post("/jobs", json=payload)

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Configuration "
        f"'{invoice_configuration['configuration_id']}' belongs to document type "
        "'invoice', not 'remittance'"
    )


def test_create_job_requires_active_configuration(app_client) -> None:
    client, _, _ = app_client

    payload = _create_job_payload()
    response = client.post("/jobs", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "No active configuration found for 'remittance'"


def test_list_jobs_returns_latest_first(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    first_response = client.post("/jobs", json=_create_job_payload(configuration["document_type"]))
    assert first_response.status_code == 201
    second_payload = _create_job_payload(configuration["document_type"])
    second_payload["created_by"] = "ops"
    second_response = client.post("/jobs", json=second_payload)
    assert second_response.status_code == 201

    response = client.get("/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["job_id"] == second_response.json()["job_id"]
    assert data[1]["job_id"] == first_response.json()["job_id"]


def test_job_ids_increment_within_same_day(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    first = client.post("/jobs", json=_create_job_payload(configuration["document_type"]))
    assert first.status_code == 201
    second = client.post("/jobs", json=_create_job_payload(configuration["document_type"]))
    assert second.status_code == 201

    first_id = first.json()["job_id"]
    second_id = second.json()["job_id"]

    assert first_id.rsplit("_", 1)[0] == second_id.rsplit("_", 1)[0]
    assert _job_sequence(second_id) == _job_sequence(first_id) + 1


def test_get_job_returns_single_job(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    create_response = client.post("/jobs", json=_create_job_payload(configuration["document_type"]))
    job = create_response.json()

    response = client.get(f"/jobs/{job['job_id']}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job["job_id"]


def test_get_job_returns_404_for_missing_job(app_client) -> None:
    client, _, _ = app_client

    response = client.get("/jobs/job_missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job 'job_missing' was not found"


def test_update_job_tracks_progress_and_completion(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    create_response = client.post("/jobs", json=_create_job_payload(configuration["document_type"]))
    job = create_response.json()

    progress_payload = {
        "status": "running",
        "logs": [
            {
                "ts": "2025-09-17T18:42:01Z",
                "level": "info",
                "message": "Detected table",
            }
        ],
    }
    progress_response = client.patch(f"/jobs/{job['job_id']}", json=progress_payload)

    assert progress_response.status_code == 200
    progress = progress_response.json()
    assert progress["status"] == "running"
    assert progress["logs"] == progress_payload["logs"]
    assert progress["outputs"] == job["outputs"]
    assert progress["metrics"] == job["metrics"]

    completion_payload = {
        "status": "completed",
        "outputs": {
            "json": {
                "uri": "var/outputs/remit_final.json",
                "expires_at": "2026-01-01T00:00:00Z",
            },
            "excel": {
                "uri": "var/outputs/remit_final.xlsx",
                "expires_at": "2026-01-01T00:00:00Z",
            },
        },
        "metrics": {
            "rows_extracted": 125,
            "processing_time_ms": 4180,
            "errors": 0,
        },
    }
    completion_response = client.patch(
        f"/jobs/{job['job_id']}", json=completion_payload
    )

    assert completion_response.status_code == 200
    completed = completion_response.json()
    assert completed["status"] == "completed"
    assert completed["outputs"] == completion_payload["outputs"]
    assert completed["metrics"] == completion_payload["metrics"]

    locked_response = client.patch(
        f"/jobs/{job['job_id']}",
        json={"status": "failed"},
    )

    assert locked_response.status_code == 409
    assert locked_response.json()["detail"] == f"Job '{job['job_id']}' can no longer be modified"


def test_update_job_rejects_invalid_status(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    create_response = client.post("/jobs", json=_create_job_payload(configuration["document_type"]))
    job = create_response.json()

    response = client.patch(
        f"/jobs/{job['job_id']}", json={"status": "unknown"}
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any(
        item.get("msg")
        == "Input should be 'pending', 'running', 'completed' or 'failed'"
        for item in detail
    )


def test_create_job_rejects_invalid_status(app_client) -> None:
    client, _, _ = app_client
    _activate_configuration(client)

    payload = _create_job_payload()
    payload["status"] = "invalid"

    response = client.post("/jobs", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any(
        item.get("msg")
        == "Input should be 'pending', 'running', 'completed' or 'failed'"
        for item in detail
    )


@pytest.mark.parametrize(
    "field, value",
    [
        ("outputs", None),
        ("metrics", None),
        ("logs", None),
    ],
)
def test_update_job_rejects_null_fields(app_client, field: str, value: Any) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    create_response = client.post("/jobs", json=_create_job_payload(configuration["document_type"]))
    job = create_response.json()

    response = client.patch(f"/jobs/{job['job_id']}", json={field: value})

    assert response.status_code == 422


def test_create_job_records_event_event(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    payload = _create_job_payload(configuration["document_type"])
    payload["status"] = "pending"

    response = client.post("/jobs", json=payload)
    assert response.status_code == 201
    job = response.json()

    events = client.get(
        "/events",
        params={"entity_type": "job", "entity_id": job["job_id"]},
    )
    assert events.status_code == 200
    payload_events = events.json()
    assert payload_events["total"] == 1
    event = payload_events["items"][0]
    assert event["event_type"] == "job.created"
    assert event["actor_label"] == payload["created_by"]
    assert event["actor_type"] == "user"
    assert event["source"] == "api"
    assert event["payload"]["document_type"] == payload["document_type"]
    assert event["payload"]["created_by"] == payload["created_by"]
    assert event["payload"]["status"] == "pending"


def test_job_updates_emit_status_and_result_events(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    payload = _create_job_payload(configuration["document_type"])
    payload["status"] = "pending"

    response = client.post("/jobs", json=payload)
    job = response.json()

    progress_response = client.patch(
        f"/jobs/{job['job_id']}",
        json={"status": "running"},
    )
    assert progress_response.status_code == 200

    completion_payload = {
        "status": "completed",
        "outputs": {
            "json": {
                "uri": "var/outputs/remit_final.json",
                "expires_at": "2026-01-01T00:00:00Z",
            }
        },
        "metrics": {
            "rows_extracted": 125,
            "processing_time_ms": 4180,
            "errors": 0,
        },
    }
    completion_response = client.patch(
        f"/jobs/{job['job_id']}",
        json=completion_payload,
    )
    assert completion_response.status_code == 200

    events = client.get(
        "/events",
        params={"entity_type": "job", "entity_id": job["job_id"]},
    )
    assert events.status_code == 200
    payload_events = events.json()
    assert payload_events["total"] == 4

    event_types = {item["event_type"] for item in payload_events["items"]}
    assert {"job.created", "job.status.running", "job.status.completed", "job.results.published"} <= event_types

    running_event = next(
        item
        for item in payload_events["items"]
        if item["event_type"] == "job.status.running"
    )
    assert running_event["payload"]["from_status"] == "pending"
    assert running_event["payload"]["to_status"] == "running"
    assert running_event["actor_label"] == "api"

    completed_event = next(
        item
        for item in payload_events["items"]
        if item["event_type"] == "job.status.completed"
    )
    assert completed_event["payload"]["from_status"] == "running"
    assert completed_event["payload"]["to_status"] == "completed"
    assert completed_event["actor_label"] == "api"

    results_event = next(
        item
        for item in payload_events["items"]
        if item["event_type"] == "job.results.published"
    )
    assert results_event["payload"]["outputs"] == completion_payload["outputs"]
    assert results_event["payload"]["metrics"] == completion_payload["metrics"]


def test_job_event_timeline_paginates_and_filters(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    payload = _create_job_payload(configuration["document_type"])
    payload["status"] = "pending"

    response = client.post("/jobs", json=payload)
    assert response.status_code == 201
    job = response.json()

    session_factory = get_sessionmaker()
    base_time = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    with session_factory() as session:
        for index in range(3):
            record_event(
                session,
                EventRecord(
                    event_type=f"job.test.{index}",
                    entity_type="job",
                    entity_id=job["job_id"],
                    source="timeline-test",
                    occurred_at=base_time + timedelta(minutes=index),
                    payload={"index": index},
                ),
            )

    response = client.get(
        f"/jobs/{job['job_id']}/events",
        params={"limit": 2, "source": "timeline-test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["entity"] == {
        "job_id": job["job_id"],
        "document_type": job["document_type"],
        "status": job["status"],
        "created_by": job["created_by"],
    }
    assert payload["total"] == 3
    assert [item["event_type"] for item in payload["items"]] == [
        "job.test.2",
        "job.test.1",
    ]

    second_page = client.get(
        f"/jobs/{job['job_id']}/events",
        params={"limit": 2, "offset": 2, "source": "timeline-test"},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["total"] == 3
    assert [item["event_type"] for item in second_payload["items"]] == [
        "job.test.0",
    ]

    filtered = client.get(
        f"/jobs/{job['job_id']}/events",
        params={
            "event_type": "job.test.1",
            "source": "timeline-test",
        },
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["event_type"] == "job.test.1"


def test_job_event_timeline_summary_tracks_updates(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    payload = _create_job_payload(configuration["document_type"])
    payload["status"] = "pending"

    response = client.post("/jobs", json=payload)
    assert response.status_code == 201
    job = response.json()

    patch_response = client.patch(
        f"/jobs/{job['job_id']}",
        json={"status": "completed"},
    )
    assert patch_response.status_code == 200
    updated = patch_response.json()

    timeline = client.get(f"/jobs/{job['job_id']}/events")
    assert timeline.status_code == 200
    payload = timeline.json()
    assert payload["entity"] == {
        "job_id": updated["job_id"],
        "document_type": updated["document_type"],
        "status": updated["status"],
        "created_by": updated["created_by"],
    }


def test_job_event_timeline_returns_404_for_missing_job(app_client) -> None:
    client, _, _ = app_client

    response = client.get("/jobs/missing/events")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job 'missing' was not found"

