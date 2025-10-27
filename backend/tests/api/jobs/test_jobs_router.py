"""Job router tests for the config version workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from backend.app.shared.db.session import get_sessionmaker
from backend.app.features.configs.service import ConfigFileService, ConfigService, ManifestService
from backend.app.features.configs.schemas import ManifestPatchRequest
from backend.tests.utils import login


pytestmark = pytest.mark.asyncio


async def _publish_config_version(
    *,
    workspace_id: str,
    author_id: str | None,
    tables: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
    logs: list[dict[str, Any]] | None = None,
) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        config_service = ConfigService(session=session)
        file_service = ConfigFileService(session=session)
        manifest_service = ManifestService(session=session)

        config = await config_service.create_config(
            workspace_id=workspace_id,
            slug=f"job-config-{datetime.now(tz=UTC).timestamp()}".replace(".", ""),
            title="Job Config",
            actor_id=author_id,
        )

        await file_service.create_draft_file(
            workspace_id=workspace_id,
            config_id=config.config_id,
            path="columns/value.py",
            code="def transform(value):\n    return value\n",
            language="python",
        )

        manifest_update = {
            "columns": [
                {
                    "key": "value",
                    "label": "Value",
                    "path": "columns/value.py",
                    "ordinal": 1,
                    "required": True,
                    "enabled": True,
                    "depends_on": [],
                }
            ],
        }
        if tables is not None:
            manifest_update["tables"] = tables
        if metrics is not None:
            manifest_update["metrics"] = metrics
        if logs is not None:
            manifest_update["logs"] = logs

        await manifest_service.patch_manifest(
            workspace_id=workspace_id,
            config_id=config.config_id,
            payload=ManifestPatchRequest(manifest=manifest_update),
        )

        published = await config_service.publish_draft(
            workspace_id=workspace_id,
            config_id=config.config_id,
            semver="1.0.0",
            message="Initial",
            actor_id=author_id,
        )

        await session.commit()
        return published.config_version_id


async def _auth_headers(async_client: AsyncClient, identity: dict[str, Any]) -> tuple[dict[str, str], str, str]:
    owner = identity["workspace_owner"]
    token, _ = await login(
        async_client,
        email=owner["email"],  # type: ignore[index]
        password=owner["password"],  # type: ignore[index]
    )
    workspace_id = identity["workspace_id"]
    return {"Authorization": f"Bearer {token}"}, workspace_id, owner["id"]  # type: ignore[return-value]


async def test_submit_job_runs_extractor(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Submitting a job should synchronously execute the processor stub."""

    headers, workspace_id, author_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    config_version_id = await _publish_config_version(
        workspace_id=workspace_id,
        author_id=author_id,
        tables=[
            {
                "title": "Line Items",
                "columns": ["description", "amount"],
                "rows": [
                    {"description": "Item A", "amount": 10},
                    {"description": "Item B", "amount": 20},
                ],
            }
        ],
        metrics={"tables_produced": 1, "rows_processed": 2},
        logs=[{"ts": "2024-01-01T00:00:00Z", "level": "info", "message": "Custom step"}],
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
        json={
            "input_document_id": document_id,
            "config_version_id": config_version_id,
        },
    )
    assert response.status_code == 201, response.text
    job_payload = response.json()
    assert job_payload["status"] == "succeeded"
    assert job_payload["config_version_id"] == config_version_id
    assert job_payload["metrics"]["tables_produced"] == 1
    assert job_payload["metrics"]["rows_processed"] == 2
    assert job_payload["run_key"]


async def test_submit_job_missing_document_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Submitting a job for a missing document should return 404."""

    headers, workspace_id, author_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"
    config_version_id = await _publish_config_version(workspace_id=workspace_id, author_id=author_id)

    response = await async_client.post(
        f"{workspace_base}/jobs",
        headers=headers,
        json={
            "input_document_id": "does-not-exist",
            "config_version_id": config_version_id,
        },
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
        json={"input_document_id": "missing"},
    )
    assert response.status_code == 422
