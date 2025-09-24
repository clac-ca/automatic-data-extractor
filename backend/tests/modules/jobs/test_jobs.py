from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select

from backend.app.core.message_hub import Message
from backend.app.db.session import get_sessionmaker
from backend.app.modules.configurations.models import Configuration
from backend.app.modules.documents.models import Document
from backend.app.modules.jobs.models import Job
from backend.app.modules.results.models import ExtractedTable
from backend.processor import ExtractionError


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _create_document(**overrides: Any) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(
            timespec="seconds"
        )
        document = Document(
            original_filename=overrides.get("original_filename", "statement.pdf"),
            content_type=overrides.get("content_type", "application/pdf"),
            byte_size=overrides.get("byte_size", 2048),
            sha256=overrides.get(
                "sha256",
                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            ),
            stored_uri=overrides.get("stored_uri", "uploads/statement.pdf"),
            metadata_=overrides.get("metadata_", {"kind": "test"}),
            expires_at=overrides.get("expires_at", expires),
            produced_by_job_id=overrides.get("produced_by_job_id"),
        )
        session.add(document)
        await session.flush()
        document_id = str(document.id)
        await session.commit()
    return document_id


async def _create_configuration(**overrides: Any) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        is_active = overrides.get("is_active", False)
        activated_at = overrides.get("activated_at")
        if activated_at is None and is_active:
            activated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        document_type = overrides.get("document_type", "bank_statement")
        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.document_type == document_type
            )
        )
        next_version = result.scalar_one_or_none() or 0
        version = overrides.get("version", next_version + 1)

        configuration = Configuration(
            document_type=document_type,
            title=overrides.get("title", "Baseline configuration"),
            version=version,
            is_active=is_active,
            activated_at=activated_at,
            payload=overrides.get("payload", {"rules": []}),
        )
        session.add(configuration)
        await session.flush()
        configuration_id = str(configuration.id)
        await session.commit()
    return configuration_id


async def _create_job(**overrides: Any) -> str:
    session_factory = get_sessionmaker()

    input_document_id = overrides.get("input_document_id")
    if input_document_id is None:
        input_document_id = await _create_document()

    async with session_factory() as session:
        job = Job(
            job_id=overrides.get("job_id", f"job_{uuid4().hex[:24]}"),
            document_type=overrides.get("document_type", "bank_statement"),
            configuration_id=overrides.get(
                "configuration_id",
                "cfg" + "0" * 22 + "1",
            ),
            configuration_version=overrides.get("configuration_version", 1),
            status=overrides.get("status", "pending"),
            created_by=overrides.get("created_by", "analyst@example.com"),
            input_document_id=input_document_id,
            metrics=overrides.get("metrics", {"pages": 3}),
            logs=overrides.get("logs", [{"message": "queued"}]),
        )
        session.add(job)
        await session.flush()
        job_id = str(job.job_id)
        await session.commit()
    return job_id


@pytest.mark.asyncio
async def test_create_job_processes_document_and_records_status(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Creating a job should kick off processing and emit status events."""

    document_id = await _create_document()
    document_type = f"bank_statement_{uuid4().hex[:6]}"
    await _create_configuration(document_type=document_type, is_active=True)

    hub = app.state.message_hub
    events: dict[str, list[Message]] = defaultdict(list)

    async def capture(message: Message) -> None:
        events[message.name].append(message)

    tracked_events = [
        "job.created",
        "job.status.running",
        "job.status.succeeded",
        "job.outputs.persisted",
        "job.outputs.viewed",
        "document.outputs.viewed",
        "table.viewed",
    ]
    for event_name in tracked_events:
        hub.subscribe(event_name, capture)
    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    try:
        response = await async_client.post(
            "/jobs",
            json={
                "document_id": document_id,
                "document_type": document_type,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        job_id = payload["job_id"]
        assert payload["status"] == "succeeded"
        assert payload["input_document_id"] == document_id
        assert payload["metrics"]["document_type"] == document_type
        assert payload["metrics"]["tables_detected"] == 1
        assert any(
            entry.get("message") == "Job processing completed successfully."
            for entry in payload["logs"]
        )

        assert events["job.created"], "Expected a job.created event to be emitted"
        assert events["job.status.running"], "Expected a job.status.running event"
        assert events["job.status.succeeded"], "Expected a job.status.succeeded event"

        succeeded_event = events["job.status.succeeded"][0]
        assert succeeded_event.payload["job_id"] == job_id
        assert succeeded_event.payload["status"] == "succeeded"

        session_factory = get_sessionmaker()
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            assert job is not None
            assert job.status == "succeeded"
            assert job.metrics.get("document_type") == document_type
            assert job.metrics.get("tables_detected") == 1
            assert any(entry.get("level") == "info" for entry in job.logs)

            result = await session.execute(
                select(ExtractedTable).where(ExtractedTable.job_id == job_id)
            )
            tables = result.scalars().all()
            assert len(tables) == 1
            persisted_table = tables[0]
            assert persisted_table.document_id == document_id
            assert persisted_table.sequence_index == 0
            assert persisted_table.row_count == len(persisted_table.sample_rows)

        assert events["job.outputs.persisted"], "Expected job outputs to be recorded"
        persisted_event = events["job.outputs.persisted"][0]
        assert persisted_event.payload["job_id"] == job_id
        assert persisted_event.payload["table_count"] == 1

        tables_response = await async_client.get(
            f"/jobs/{job_id}/tables",
            headers=headers,
        )
        assert tables_response.status_code == 200
        tables_payload = tables_response.json()
        assert len(tables_payload) == 1
        table_payload = tables_payload[0]
        assert table_payload["job_id"] == job_id
        assert table_payload["document_id"] == document_id
        assert table_payload["sequence_index"] == 0
        assert table_payload["columns"] == ["field", "value"]
        assert events["job.outputs.viewed"], "Expected job.outputs.viewed to be emitted"

        table_id = table_payload["table_id"]
        detail_response = await async_client.get(
            f"/jobs/{job_id}/tables/{table_id}",
            headers=headers,
        )
        assert detail_response.status_code == 200
        assert events["table.viewed"], "Expected table.viewed to be emitted"

        document_tables = await async_client.get(
            f"/documents/{document_id}/tables",
            headers=headers,
        )
        assert document_tables.status_code == 200
        document_tables_payload = document_tables.json()
        assert document_tables_payload
        assert document_tables_payload[0]["table_id"] == table_id
        assert events["document.outputs.viewed"], "Expected document.outputs.viewed event"

        timeline = await async_client.get(
            f"/jobs/{job_id}/events",
            headers=headers,
        )
        assert timeline.status_code == 200
        timeline_events = timeline.json()
        assert timeline_events, "Expected at least one timeline event"
        event_types = [item["event_type"] for item in timeline_events]
        assert "job.status.succeeded" in event_types
        assert "job.status.running" in event_types
        assert "job.created" in event_types
        assert "job.outputs.persisted" in event_types
        assert "job.outputs.viewed" in event_types
    finally:
        for event_name in tracked_events:
            hub.unsubscribe(event_name, capture)


@pytest.mark.asyncio
async def test_job_processing_failure_records_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Processor failures should mark the job as failed and emit events."""

    document_id = await _create_document()
    document_type = f"invoice_{uuid4().hex[:6]}"
    await _create_configuration(document_type=document_type, is_active=True)

    async def fail_run_extraction(_: Any) -> None:
        raise ExtractionError("forced failure")

    monkeypatch.setattr(
        "backend.app.modules.jobs.worker.run_extraction",
        fail_run_extraction,
    )

    hub = app.state.message_hub
    events: dict[str, list[Message]] = defaultdict(list)

    async def capture(message: Message) -> None:
        events[message.name].append(message)

    hub.subscribe("job.status.running", capture)
    hub.subscribe("job.status.failed", capture)

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    try:
        response = await async_client.post(
            "/jobs",
            json={
                "document_id": document_id,
                "document_type": document_type,
            },
            headers=headers,
        )
    finally:
        hub.unsubscribe("job.status.running", capture)
        hub.unsubscribe("job.status.failed", capture)

    assert response.status_code == 201, response.text
    payload = response.json()
    job_id = payload["job_id"]
    assert payload["status"] == "failed"
    assert any(entry.get("level") == "error" for entry in payload["logs"])

    assert events["job.status.running"], "Expected a job.status.running event"
    assert events["job.status.failed"], "Expected a job.status.failed event"

    failure_event = events["job.status.failed"][0]
    assert failure_event.payload["job_id"] == job_id
    assert failure_event.payload["status"] == "failed"

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert any(entry.get("level") == "error" for entry in job.logs)
        result = await session.execute(
            select(ExtractedTable).where(ExtractedTable.job_id == job_id)
        )
        assert result.scalars().all() == []

    timeline = await async_client.get(
        f"/jobs/{job_id}/events",
        headers=headers,
    )
    assert timeline.status_code == 200
    event_types = [item["event_type"] for item in timeline.json()]
    assert "job.status.failed" in event_types
    assert "job.status.running" in event_types


@pytest.mark.asyncio
async def test_list_job_tables_unknown_job_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Listing tables for a missing job should return 404."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.get("/jobs/job_missing/tables", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_read_job_table_unknown_table_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Requesting a table that does not exist should return 404."""

    document_id = await _create_document()
    document_type = f"statement_{uuid4().hex[:6]}"
    await _create_configuration(document_type=document_type, is_active=True)

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.post(
        "/jobs",
        json={"document_id": document_id, "document_type": document_type},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["job_id"]

    missing_table_response = await async_client.get(
        f"/jobs/{job_id}/tables/table_missing",
        headers=headers,
    )
    assert missing_table_response.status_code == 404


@pytest.mark.asyncio
async def test_list_document_tables_unknown_document_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Listing tables for a missing document should return 404."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.get(
        "/documents/doc_missing/tables",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_job_missing_document_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Attempting to queue a job without an input document should fail."""

    document_type = f"invoice_{uuid4().hex[:6]}"
    await _create_configuration(document_type=document_type, is_active=True)

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.post(
        "/jobs",
        json={
            "document_id": "doc_missing",
            "document_type": document_type,
        },
        headers=headers,
    )

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "input_document_not_found"


@pytest.mark.asyncio
async def test_create_job_without_active_configuration_returns_conflict(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Missing active configurations should yield a conflict response."""

    document_id = await _create_document()
    document_type = f"invoice_{uuid4().hex[:6]}"
    await _create_configuration(document_type=document_type, is_active=False)

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.post(
        "/jobs",
        json={
            "document_id": document_id,
            "document_type": document_type,
        },
        headers=headers,
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "active_configuration_missing"


@pytest.mark.asyncio
async def test_create_job_configuration_mismatch_returns_conflict(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Explicit configuration identifiers must match the document type."""

    document_id = await _create_document()
    document_type = f"invoice_{uuid4().hex[:6]}"
    other_document_type = f"statement_{uuid4().hex[:6]}"
    await _create_configuration(document_type=document_type, is_active=True)
    mismatch_configuration = await _create_configuration(
        document_type=other_document_type, is_active=True
    )

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.post(
        "/jobs",
        json={
            "document_id": document_id,
            "document_type": document_type,
            "configuration_id": mismatch_configuration,
        },
        headers=headers,
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "configuration_mismatch"


@pytest.mark.asyncio
async def test_list_jobs_emits_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Listing jobs should emit an event and return results."""

    job_id = await _create_job()

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("jobs.listed", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])

        response = await async_client.get(
            "/jobs",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Workspace-ID": seed_identity["workspace_id"],
            },
        )
    finally:
        hub.unsubscribe("jobs.listed", capture)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(item["job_id"] == job_id for item in payload)

    assert len(events) == 1
    event = events[0]
    assert event.name == "jobs.listed"
    assert event.payload["count"] >= 1
    assert event.metadata.get("workspace_id") == seed_identity["workspace_id"]
    assert event.metadata.get("actor_type") == "user"


@pytest.mark.asyncio
async def test_read_job_emits_view_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Fetching a single job should emit a view event."""

    job_id = await _create_job()

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("job.viewed", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])

        response = await async_client.get(
            f"/jobs/{job_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Workspace-ID": seed_identity["workspace_id"],
            },
        )
    finally:
        hub.unsubscribe("job.viewed", capture)

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert events, "Expected at least one event to be emitted"
    event = events[0]
    assert event.name == "job.viewed"
    assert event.payload["job_id"] == job_id
    assert event.metadata.get("workspace_id") == seed_identity["workspace_id"]


@pytest.mark.asyncio
async def test_read_job_not_found_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Unknown job identifiers should yield a 404 response."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        "/jobs/job_missing",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_events_timeline_returns_persisted_events(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Timeline endpoint should return events captured for a job."""

    job_id = await _create_job()
    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.get(f"/jobs/{job_id}", headers=headers)
    assert response.status_code == 200

    timeline = await async_client.get(
        f"/jobs/{job_id}/events",
        headers=headers,
    )

    assert timeline.status_code == 200
    events = timeline.json()
    assert isinstance(events, list)
    assert events, "Expected at least one persisted event"

    first = events[0]
    assert first["event_type"] == "job.viewed"
    assert first["entity_id"] == job_id
    assert first["payload"]["job_id"] == job_id
    assert first["actor_type"] == "user"


@pytest.mark.asyncio
async def test_job_events_timeline_missing_job_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Timeline request for unknown jobs should return 404."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        "/jobs/job_missing/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 404
