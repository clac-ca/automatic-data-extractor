from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from backend.api.db.session import get_sessionmaker
from backend.api.modules.configurations.models import Configuration
from backend.api.modules.workspaces.models import WorkspaceMembership


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _create_configuration(
    *, payload: dict[str, Any] | None = None, document_type: str = "invoice"
) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.document_type == document_type
            )
        )
        next_version = result.scalar_one_or_none() or 0
        version = next_version + 1

        configuration = Configuration(
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


async def _grant_permissions(
    user_id: str, workspace_id: str, permissions: Iterable[str]
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        membership = result.scalar_one()
        current = set(membership.permissions or [])
        current.update(permissions)
        membership.permissions = sorted(current)
        await session.commit()


@pytest.mark.asyncio
async def test_results_end_to_end(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Upload → job → results should expose stored tables for succeeded jobs."""

    configuration_id = await _create_configuration(
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
    workspace_id = seed_identity["workspace_id"]
    await _grant_permissions(
        actor["id"],
        workspace_id,
        {
            "workspace:jobs:write",
            "workspace:jobs:read",
            "workspace:documents:read",
        },
    )

    token = await _login(async_client, actor["email"], actor["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": workspace_id,
    }

    upload = await async_client.post(
        "/documents",
        headers=headers,
        files={"file": ("input.txt", b"payload", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    job_response = await async_client.post(
        "/jobs",
        headers=headers,
        json={
            "input_document_id": document_id,
            "configuration_id": configuration_id,
        },
    )
    assert job_response.status_code == 201, job_response.text
    job_payload = job_response.json()
    job_id = job_payload["job_id"]

    tables_response = await async_client.get(
        f"/jobs/{job_id}/tables",
        headers=headers,
    )
    assert tables_response.status_code == 200, tables_response.text
    tables = tables_response.json()
    assert tables, "Expected at least one extracted table"
    assert tables[0]["document_id"] == document_id

    table_id = tables[0]["table_id"]
    table_detail = await async_client.get(
        f"/jobs/{job_id}/tables/{table_id}",
        headers=headers,
    )
    assert table_detail.status_code == 200, table_detail.text
    assert table_detail.json()["table_id"] == table_id

    document_tables = await async_client.get(
        f"/documents/{document_id}/tables",
        headers=headers,
    )
    assert document_tables.status_code == 200, document_tables.text
    assert document_tables.json()[0]["table_id"] == table_id


@pytest.mark.asyncio
async def test_job_tables_missing_job_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    actor = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    await _grant_permissions(
        actor["id"],
        workspace_id,
        {"workspace:jobs:read"},
    )

    token = await _login(async_client, actor["email"], actor["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": workspace_id,
    }

    response = await async_client.get(
        "/jobs/missing/tables",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_tables_failed_job_returns_409(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    configuration_id = await _create_configuration(
        payload={
            "simulate_failure": True,
            "failure_message": "Stub failure",
        }
    )

    actor = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    await _grant_permissions(
        actor["id"],
        workspace_id,
        {"workspace:jobs:write", "workspace:jobs:read"},
    )

    token = await _login(async_client, actor["email"], actor["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": workspace_id,
    }

    upload = await async_client.post(
        "/documents",
        headers=headers,
        files={"file": ("input.txt", b"payload", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    job_response = await async_client.post(
        "/jobs",
        headers=headers,
        json={
            "input_document_id": document_id,
            "configuration_id": configuration_id,
        },
    )
    assert job_response.status_code == 500
    detail = job_response.json()["detail"]
    job_id = detail["job_id"]

    tables_response = await async_client.get(
        f"/jobs/{job_id}/tables",
        headers=headers,
    )
    assert tables_response.status_code == 409
    payload = tables_response.json()["detail"]
    assert payload["error"] == "job_results_unavailable"
    assert payload["status"] == "failed"


@pytest.mark.asyncio
async def test_document_tables_deleted_document_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    configuration_id = await _create_configuration()

    actor = seed_identity["workspace_owner"]
    workspace_id = seed_identity["workspace_id"]
    await _grant_permissions(
        actor["id"],
        workspace_id,
        {
            "workspace:jobs:write",
            "workspace:jobs:read",
            "workspace:documents:read",
            "workspace:documents:write",
        },
    )

    token = await _login(async_client, actor["email"], actor["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": workspace_id,
    }

    upload = await async_client.post(
        "/documents",
        headers=headers,
        files={"file": ("input.txt", b"payload", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    job_response = await async_client.post(
        "/jobs",
        headers=headers,
        json={
            "input_document_id": document_id,
            "configuration_id": configuration_id,
        },
    )
    assert job_response.status_code == 201, job_response.text

    delete_response = await async_client.request(
        "DELETE",
        f"/documents/{document_id}",
        headers=headers,
        json={"reason": "cleanup"},
    )
    assert delete_response.status_code == 204

    document_tables = await async_client.get(
        f"/documents/{document_id}/tables",
        headers=headers,
    )
    assert document_tables.status_code == 404
