import io
from datetime import datetime, timezone
from typing import Any

from backend.app.auth.email import canonicalize_email
from backend.app.db import get_sessionmaker
from backend.app.models import User
from backend.tests.conftest import DEFAULT_USER_EMAIL

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


def _upload_document(
    client,
    *,
    filename: str = "input.pdf",
    data: bytes = b"PDF",
    content_type: str = "application/pdf",
    produced_by_job_id: str | None = None,
) -> dict[str, Any]:
    files = {"file": (filename, io.BytesIO(data), content_type)}
    form: dict[str, Any] = {}
    if produced_by_job_id is not None:
        form["produced_by_job_id"] = produced_by_job_id
    response = client.post("/documents", files=files, data=form)
    assert response.status_code == 201
    return response.json()


def _create_job(
    client,
    configuration: dict[str, Any],
    input_document: dict[str, Any],
    *,
    created_by: str = "jkropp",
    status: str = "running",
    metrics: dict[str, Any] | None = None,
    logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "document_type": configuration["document_type"],
        "created_by": created_by,
        "input_document_id": input_document["document_id"],
        "status": status,
    }
    if metrics is not None:
        payload["metrics"] = metrics
    if logs is not None:
        payload["logs"] = logs

    response = client.post("/jobs", json=payload)
    assert response.status_code == 201
    return response.json()


def _default_user_id() -> str:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        user = (
            db.query(User)
            .filter(User.email_canonical == canonicalize_email(DEFAULT_USER_EMAIL))
            .one()
        )
        return user.user_id


def _soft_delete_document(client, document_id: str, *, deleted_by: str = "tester") -> None:
    payload = {"deleted_by": deleted_by}
    response = client.request("DELETE", f"/documents/{document_id}", json=payload)
    assert response.status_code == 200


def test_create_job_returns_input_projection(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)
    document = _upload_document(client)

    metrics = {"rows_extracted": 12}
    logs = [
        {
            "ts": "2024-01-01T12:00:00Z",
            "level": "info",
            "message": "Job created",
        }
    ]

    response = client.post(
        "/jobs",
        json={
            "document_type": configuration["document_type"],
            "created_by": "jkropp",
            "input_document_id": document["document_id"],
            "status": "running",
            "metrics": metrics,
            "logs": logs,
        },
    )

    assert response.status_code == 201
    job = response.json()

    assert job["document_type"] == configuration["document_type"]
    assert job["configuration_id"] == configuration["configuration_id"]
    assert job["status"] == "running"
    assert job["metrics"] == metrics
    assert job["logs"] == logs
    assert job["output_documents"] == []
    assert "legacy_input" not in job

    input_document = job["input_document"]
    assert input_document["document_id"] == document["document_id"]
    assert input_document["is_deleted"] is False
    assert input_document["download_url"].endswith(
        f"/documents/{document['document_id']}/download"
    )


def test_create_job_rejects_unknown_input_document(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)

    payload = {
        "document_type": configuration["document_type"],
        "created_by": "jkropp",
        "input_document_id": "01J9UNKNOWN0000000000000000",
    }

    response = client.post("/jobs", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"] == "Document '01J9UNKNOWN0000000000000000' was not found"


def test_get_job_includes_outputs_and_deleted_state(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)
    input_document = _upload_document(client)
    job = _create_job(client, configuration, input_document)

    first_output = _upload_document(
        client,
        filename="remit.json",
        data=b"{}",
        content_type="application/json",
        produced_by_job_id=job["job_id"],
    )
    second_output = _upload_document(
        client,
        filename="remit.xlsx",
        data=b"binary",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        produced_by_job_id=job["job_id"],
    )

    _soft_delete_document(client, first_output["document_id"])

    response = client.get(f"/jobs/{job['job_id']}")
    assert response.status_code == 200
    payload = response.json()

    output_documents = payload["output_documents"]
    assert [doc["document_id"] for doc in output_documents] == [
        first_output["document_id"],
        second_output["document_id"],
    ]

    deleted = output_documents[0]
    assert deleted["is_deleted"] is True
    assert deleted.get("download_url") is None

    active = output_documents[1]
    assert active["is_deleted"] is False
    assert active["download_url"].endswith(
        f"/documents/{second_output['document_id']}/download"
    )

def test_list_jobs_filters_by_input_document(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)
    input_a = _upload_document(client, filename="a.pdf")
    input_b = _upload_document(client, filename="b.pdf")

    job_a = _create_job(client, configuration, input_a, created_by="alpha")
    _create_job(client, configuration, input_b, created_by="beta")

    response = client.get(
        "/jobs",
        params={"input_document_id": input_a["document_id"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert [item["job_id"] for item in data] == [job_a["job_id"]]


def test_document_history_lists_jobs(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)
    input_document = _upload_document(client)

    first_job = _create_job(client, configuration, input_document, created_by="first")
    second_job = _create_job(client, configuration, input_document, created_by="second")

    output_document = _upload_document(
        client,
        filename="output.json",
        data=b"{}",
        content_type="application/json",
        produced_by_job_id=second_job["job_id"],
    )

    as_input = client.get(f"/documents/{input_document['document_id']}/jobs")
    assert as_input.status_code == 200
    history = as_input.json()
    assert history["document_id"] == input_document["document_id"]
    assert [job["job_id"] for job in history["input_to_jobs"]] == [
        second_job["job_id"],
        first_job["job_id"],
    ]
    assert history.get("produced_by_job") is None

    as_output = client.get(f"/documents/{output_document['document_id']}/jobs")
    assert as_output.status_code == 200
    output_history = as_output.json()
    assert output_history["input_to_jobs"] == []
    assert output_history["produced_by_job"]["job_id"] == second_job["job_id"]


def test_documents_filter_by_produced_by_job(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)
    input_document = _upload_document(client)
    job = _create_job(client, configuration, input_document)

    first_output = _upload_document(
        client,
        filename="output-1.json",
        data=b"{}",
        produced_by_job_id=job["job_id"],
    )
    second_output = _upload_document(
        client,
        filename="output-2.json",
        data=b"{}",
        produced_by_job_id=job["job_id"],
    )

    response = client.get(
        "/documents",
        params={"produced_by_job_id": job["job_id"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert [doc["document_id"] for doc in data] == [
        second_output["document_id"],
        first_output["document_id"],
    ]


def test_upload_document_rejects_unknown_job_reference(app_client) -> None:
    client, _, _ = app_client
    files = {"file": ("output.json", io.BytesIO(b"{}"), "application/json")}
    response = client.post(
        "/documents",
        files=files,
        data={"produced_by_job_id": "job_2024_01_01_0001"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_job_reference"
    assert detail["message"] == "Job 'job_2024_01_01_0001' was not found"


def test_update_job_updates_metrics(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)
    document = _upload_document(client)
    job = _create_job(client, configuration, document)

    update = {
        "metrics": {"rows_extracted": 5},
        "logs": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": "info",
                "message": "metrics updated",
            }
        ],
    }

    response = client.patch(f"/jobs/{job['job_id']}", json=update)
    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"] == update["metrics"]
    assert payload["logs"] == update["logs"]


def test_job_events_default_actor_metadata(app_client) -> None:
    client, _, _ = app_client
    configuration = _activate_configuration(client)
    document = _upload_document(client)
    user_id = _default_user_id()

    job = _create_job(client, configuration, document)

    initial_events = client.get(
        "/events",
        params={"entity_type": "job", "entity_id": job["job_id"]},
    )
    assert initial_events.status_code == 200
    initial_payload = initial_events.json()
    assert initial_payload["total"] == 1
    created_event = next(
        item
        for item in initial_payload["items"]
        if item["event_type"] == "job.created"
    )
    assert created_event["actor_type"] == "user"
    assert created_event["actor_id"] == user_id
    assert created_event["actor_label"] == DEFAULT_USER_EMAIL

    update_response = client.patch(
        f"/jobs/{job['job_id']}", json={"status": "completed"}
    )
    assert update_response.status_code == 200

    updated_events = client.get(
        "/events",
        params={"entity_type": "job", "entity_id": job["job_id"]},
    )
    assert updated_events.status_code == 200
    updated_payload = updated_events.json()
    assert updated_payload["total"] == 2
    status_event = next(
        item
        for item in updated_payload["items"]
        if item["event_type"] == "job.status.completed"
    )
    assert status_event["actor_type"] == "user"
    assert status_event["actor_id"] == user_id
    assert status_event["actor_label"] == DEFAULT_USER_EMAIL

