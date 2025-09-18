"""Tests for the job API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
import re


def _activate_revision(
    client, *, document_type: str = "remittance", title: str = "Active revision"
) -> dict[str, Any]:
    payload = {
        "document_type": document_type,
        "title": title,
        "payload": {"rules": []},
        "is_active": True,
    }
    response = client.post("/configuration-revisions", json=payload)
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


def test_create_job_uses_active_revision(app_client) -> None:
    client, _, _ = app_client
    revision = _activate_revision(client)

    payload = _create_job_payload(revision["document_type"])
    response = client.post("/jobs", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert re.fullmatch(r"job_\d{4}_\d{2}_\d{2}_\d{4}", data["job_id"])
    assert data["document_type"] == payload["document_type"]
    assert data["configuration_revision"] == revision["revision_number"]
    assert data["status"] == payload["status"]
    assert data["created_by"] == payload["created_by"]
    assert data["input"] == payload["input"]
    assert data["outputs"] == payload["outputs"]
    assert data["metrics"] == payload["metrics"]
    assert data["logs"] == payload["logs"]
    datetime.fromisoformat(data["created_at"])
    datetime.fromisoformat(data["updated_at"])


def test_create_job_with_explicit_revision(app_client) -> None:
    client, _, _ = app_client
    active = _activate_revision(client, title="Draft to activate")
    draft_payload = {
        "document_type": active["document_type"],
        "title": "Historical revision",
        "payload": {"rules": ["legacy"]},
    }
    draft_response = client.post("/configuration-revisions", json=draft_payload)
    assert draft_response.status_code == 201
    draft_revision = draft_response.json()

    payload = _create_job_payload(active["document_type"])
    payload["configuration_revision_id"] = draft_revision["configuration_revision_id"]
    payload["status"] = "pending"

    response = client.post("/jobs", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["configuration_revision"] == draft_revision["revision_number"]
    assert data["status"] == "pending"


def test_create_job_rejects_revision_for_other_document_type(app_client) -> None:
    client, _, _ = app_client
    invoice_revision = _activate_revision(client, document_type="invoice")
    remittance_revision = _activate_revision(client, document_type="remittance")

    payload = _create_job_payload(remittance_revision["document_type"])
    payload["configuration_revision_id"] = invoice_revision["configuration_revision_id"]

    response = client.post("/jobs", json=payload)

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Configuration revision "
        f"'{invoice_revision['configuration_revision_id']}' belongs to document type "
        "'invoice', not 'remittance'"
    )


def test_create_job_requires_active_revision(app_client) -> None:
    client, _, _ = app_client

    payload = _create_job_payload()
    response = client.post("/jobs", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "No active configuration revision found for 'remittance'"


def test_list_jobs_returns_latest_first(app_client) -> None:
    client, _, _ = app_client
    revision = _activate_revision(client)

    first_response = client.post("/jobs", json=_create_job_payload(revision["document_type"]))
    assert first_response.status_code == 201
    second_payload = _create_job_payload(revision["document_type"])
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
    revision = _activate_revision(client)

    first = client.post("/jobs", json=_create_job_payload(revision["document_type"]))
    assert first.status_code == 201
    second = client.post("/jobs", json=_create_job_payload(revision["document_type"]))
    assert second.status_code == 201

    first_id = first.json()["job_id"]
    second_id = second.json()["job_id"]

    assert first_id.rsplit("_", 1)[0] == second_id.rsplit("_", 1)[0]
    assert _job_sequence(second_id) == _job_sequence(first_id) + 1


def test_get_job_returns_single_job(app_client) -> None:
    client, _, _ = app_client
    revision = _activate_revision(client)

    create_response = client.post("/jobs", json=_create_job_payload(revision["document_type"]))
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
    revision = _activate_revision(client)

    create_response = client.post("/jobs", json=_create_job_payload(revision["document_type"]))
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
    revision = _activate_revision(client)

    create_response = client.post("/jobs", json=_create_job_payload(revision["document_type"]))
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
    _activate_revision(client)

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
    revision = _activate_revision(client)

    create_response = client.post("/jobs", json=_create_job_payload(revision["document_type"]))
    job = create_response.json()

    response = client.patch(f"/jobs/{job['job_id']}", json={field: value})

    assert response.status_code == 422

