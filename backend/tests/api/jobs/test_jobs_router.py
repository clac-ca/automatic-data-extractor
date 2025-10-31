import base64
import io
import json
from typing import Any
from zipfile import ZipFile

import pytest
from httpx import AsyncClient

from backend.tests.utils import login

pytestmark = pytest.mark.asyncio


async def _auth(async_client: AsyncClient, identity: dict[str, Any]) -> tuple[dict[str, str], str]:
    owner = identity["workspace_owner"]
    token, _ = await login(
        async_client,
        email=owner["email"],  # type: ignore[index]
        password=owner["password"],  # type: ignore[index]
    )
    return {"Authorization": f"Bearer {token}"}, identity["workspace_id"]  # type: ignore[return-value]


def _package(manifest: dict[str, Any], name: str) -> dict[str, str]:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("columns/example.py", "def detect(*_, **__):\n    return {}\n")
    payload = base64.b64encode(buffer.getvalue()).decode()
    return {"filename": f"{name}.zip", "content": payload}


async def _create_config(
    async_client: AsyncClient,
    headers: dict[str, str],
    workspace_id: str,
) -> tuple[str, dict[str, Any]]:
    base = f"/api/v1/workspaces/{workspace_id}/configs"
    manifest = {
        "target_fields": ["member_id", "name"],
        "engine": {"defaults": {"min_mapping_confidence": 0.5}},
    }
    created = await async_client.post(
        base,
        headers=headers,
        json={
            "slug": "job-config",
            "title": "Job Config",
            "package": _package(manifest, "job-config"),
            "manifest": manifest,
        },
    )
    created.raise_for_status()
    detail = created.json()
    version = detail["versions"][0]
    return version["config_version_id"], manifest


async def test_job_submission_produces_artifacts(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    headers, workspace_id = await _auth(async_client, seed_identity)
    version_id, manifest = await _create_config(async_client, headers, workspace_id)

    base = f"/api/v1/workspaces/{workspace_id}/jobs"
    submitted = await async_client.post(
        base,
        headers=headers,
        json={"config_version_id": version_id},
    )
    assert submitted.status_code == 201, submitted.text
    job_payload = submitted.json()
    job_id = job_payload["job_id"]
    assert job_payload["status"] == "succeeded"
    assert job_payload["artifact_uri"].endswith("artifact.json")
    assert job_payload["output_uri"].endswith("normalized.xlsx")

    detail = await async_client.get(f"{base}/{job_id}", headers=headers)
    detail.raise_for_status()
    detail_payload = detail.json()
    assert detail_payload["config_version"]["config_version_id"] == version_id

    artifact = await async_client.get(f"{base}/{job_id}/artifact", headers=headers)
    artifact.raise_for_status()
    artifact_payload = artifact.json()
    assert artifact_payload["config"]["manifest"] == manifest

    output = await async_client.get(f"{base}/{job_id}/output", headers=headers)
    output.raise_for_status()
    assert output.content
    assert output.headers["content-type"] in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }
