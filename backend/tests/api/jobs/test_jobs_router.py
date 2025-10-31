"""API contract tests for job submission endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from backend.app.features.configs.service import ConfigService
from backend.app.shared.db.session import get_sessionmaker
from backend.tests.utils import login


pytestmark = pytest.mark.asyncio


async def _activate_default_config(
    *, workspace_id: str, author_id: str | None
) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        service = ConfigService(session=session)
        record = await service.create_config(
            workspace_id=workspace_id,
            title="Job Config",
            actor_id=author_id,
        )
        await service.activate_config(
            workspace_id=workspace_id,
            config_id=record.config_id,
            actor_id=author_id,
        )
        await session.commit()
        return record.config_id


async def _auth_headers(
    async_client: AsyncClient, identity: dict[str, Any]
) -> tuple[dict[str, str], str, str]:
    owner = identity["workspace_owner"]
    token, _ = await login(
        async_client,
        email=owner["email"],  # type: ignore[index]
        password=owner["password"],  # type: ignore[index]
    )
    workspace_id = identity["workspace_id"]
    csrf_token = async_client.cookies.get("backend_app_csrf")
    headers = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return headers, workspace_id, owner["id"]  # type: ignore[return-value]


async def test_submit_job_runs_extractor(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Submitting a job should synchronously execute the stub processor."""

    headers, workspace_id, author_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    config_id = await _activate_default_config(
        workspace_id=workspace_id,
        author_id=author_id,
    )

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
        json={"input_document_id": document_id},
    )
    assert response.status_code == 201, response.text
    job_payload = response.json()
    assert job_payload["status"] == "succeeded"
    assert job_payload["config_id"] == config_id
    assert job_payload["metrics"]["duration_ms"] >= 0
    assert job_payload["run_key"]


async def test_submit_job_missing_document_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Submitting a job for a missing document should return 404."""

    headers, workspace_id, author_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"
    await _activate_default_config(workspace_id=workspace_id, author_id=author_id)

    response = await async_client.post(
        f"{workspace_base}/jobs",
        headers=headers,
        json={"input_document_id": "does-not-exist"},
    )
    assert response.status_code == 404


async def test_submit_job_missing_body_fields_returns_422(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """FastAPI should reject incomplete job submissions with a 422 error."""

    headers, workspace_id, _ = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    response = await async_client.post(
        f"{workspace_base}/jobs",
        headers=headers,
        json={},
    )
    assert response.status_code == 422

