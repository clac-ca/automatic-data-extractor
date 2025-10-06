from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.features.configurations.models import Configuration
from app.features.workspaces.models import WorkspaceMembership


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get("ade_session")
    assert token, "Session cookie missing"
    return token


async def _create_configuration(
    *,
    workspace_id: str,
    payload: dict[str, Any] | None = None,
    document_type: str = "invoice",
) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.workspace_id == workspace_id,
                Configuration.document_type == document_type,
            )
        )
        next_version = result.scalar_one_or_none() or 0
        version = next_version + 1

        configuration = Configuration(
            workspace_id=workspace_id,
            document_type=document_type,
            title="Test configuration",
            version=version,
            is_active=False,
            activated_at=None,
            payload=payload or {},
        )
        session.add(configuration)
        await session.flush()
        configuration_id = str(configuration.id)
        await session.commit()
    return configuration_id


async def _grant_job_permission(user_id: str, workspace_id: str) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        membership = result.scalar_one()
        permissions = set(membership.permissions or [])
        permissions.add("workspace:jobs:write")
        membership.permissions = sorted(permissions)
        await session.commit()


@pytest.mark.asyncio
async def test_submit_job_runs_extractor(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Submitting a job should synchronously execute the processor stub."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(
        workspace_id=workspace_id,
        payload={
            "tables": [
                {
                    "title": "Line Items",
                    "columns": ["description", "amount"],
                    "rows": [
                        {"description": "Item A", "amount": 10},
                        {"description": "Item B", "amount": 20},
                    ],
                }
            ],
            "metrics": {"rows_processed": 2, "tables_produced": 1},
            "logs": [
                {
                    "ts": "2024-01-01T00:00:00Z",
                    "level": "info",
                    "message": "Custom step executed",
                }
            ],
        }
    )

    actor = seed_identity["workspace_owner"]
    await _grant_job_permission(actor["id"], seed_identity["workspace_id"])
    token = await _login(async_client, actor["email"], actor["password"])
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("input.txt", b"payload", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    response = await async_client.post(
        f"{workspace_base}/jobs",
        headers=headers,
        json={
            "input_document_id": document_id,
            "configuration_id": configuration_id,
        },
    )
    assert response.status_code == 201, response.text
    job_payload = response.json()
    job_id = job_payload["job_id"]

    assert job_payload["status"] == "succeeded"
    assert job_payload["configuration_id"] == configuration_id
    assert job_payload["metrics"]["tables_produced"] == 1
    assert job_payload["metrics"]["rows_processed"] == 2
    assert len(job_payload["logs"]) >= 2

    listing = await async_client.get(f"{workspace_base}/jobs", headers=headers)
    assert listing.status_code == 200
    jobs = listing.json()
    assert any(item["job_id"] == job_id for item in jobs)

    detail = await async_client.get(
        f"{workspace_base}/jobs/{job_id}", headers=headers
    )
    assert detail.status_code == 200
    assert detail.json()["metrics"]["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_submit_job_missing_document_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Submitting a job for a missing document should return 404."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(workspace_id=workspace_id)
    actor = seed_identity["workspace_owner"]
    await _grant_job_permission(actor["id"], seed_identity["workspace_id"])
    token = await _login(async_client, actor["email"], actor["password"])
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    response = await async_client.post(
        f"{workspace_base}/jobs",
        headers=headers,
        json={
            "input_document_id": "does-not-exist",
            "configuration_id": configuration_id,
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_job_missing_body_fields_returns_422(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """FastAPI should reject incomplete job submissions with a 422 error."""

    actor = seed_identity["workspace_owner"]
    await _grant_job_permission(actor["id"], seed_identity["workspace_id"])
    token = await _login(async_client, actor["email"], actor["password"])
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    response = await async_client.post(
        f"{workspace_base}/jobs",
        headers=headers,
        json={},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    missing_fields = {entry["loc"][-1] for entry in detail}
    assert "input_document_id" in missing_fields
    assert "configuration_id" in missing_fields


@pytest.mark.asyncio
async def test_submit_job_missing_configuration_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Unknown configuration identifiers should yield 404."""

    actor = seed_identity["workspace_owner"]
    await _grant_job_permission(actor["id"], seed_identity["workspace_id"])
    token = await _login(async_client, actor["email"], actor["password"])
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("input.txt", b"payload", "text/plain")},
    )
    document_id = upload.json()["document_id"]

    response = await async_client.post(
        f"{workspace_base}/jobs",
        headers=headers,
        json={
            "input_document_id": document_id,
            "configuration_id": "missing",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_job_processor_failure_returns_500(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Processor failures should mark the job failed and surface the error."""

    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _create_configuration(
        workspace_id=workspace_id,
        payload={
            "simulate_failure": True,
            "failure_message": "Stub failure",
        }
    )

    actor = seed_identity["workspace_owner"]
    await _grant_job_permission(actor["id"], seed_identity["workspace_id"])
    token = await _login(async_client, actor["email"], actor["password"])
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("input.txt", b"payload", "text/plain")},
    )
    document_id = upload.json()["document_id"]

    response = await async_client.post(
        f"{workspace_base}/jobs",
        headers=headers,
        json={
            "input_document_id": document_id,
            "configuration_id": configuration_id,
        },
    )
    assert response.status_code == 500
    payload = response.json()["detail"]
    job_id = payload["job_id"]
    assert payload["error"] == "job_failed"
    assert payload["message"] == "Stub failure"

    detail = await async_client.get(
        f"{workspace_base}/jobs/{job_id}", headers=headers
    )
    assert detail.status_code == 200
    record = detail.json()
    assert record["status"] == "failed"
    assert record["metrics"]["error"] == "Stub failure"
    assert any("Stub failure" in entry["message"] for entry in record["logs"])

