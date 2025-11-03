import io
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

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


def _manifest(title: str, fields: list[str]) -> dict[str, Any]:
    return {
        "config_script_api_version": "1",
        "info": {
            "schema": "ade.manifest/v1.0",
            "title": title,
            "version": "1.0.0",
        },
        "engine": {
            "defaults": {
                "timeout_ms": 120000,
                "memory_mb": 256,
                "runtime_network_access": False,
                "mapping_score_threshold": 0.0,
            },
            "writer": {
                "mode": "row_streaming",
                "append_unmapped_columns": True,
                "unmapped_prefix": "raw_",
                "output_sheet": "Normalized",
            },
        },
        "env": {},
        "hooks": {
            "on_activate": [],
            "on_job_start": [],
            "on_after_extract": [],
            "on_job_end": [],
        },
        "columns": {
            "order": fields,
            "meta": {
                field: {
                    "label": field.title(),
                    "required": True,
                    "enabled": True,
                    "script": f"columns/{field}.py",
                }
                for field in fields
            },
        },
    }


def _package(manifest: dict[str, Any], name: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("columns/__init__.py", "")
        for field in manifest["columns"]["order"]:
            archive.writestr(
                f"columns/{field}.py",
                (
                    "def detect_default(*, header, values_sample, column_index, table, job_context, env):\n"
                    f"    return {{'scores': {{'{field}': 1.0}}}}\n\n"
                    "def transform(*, header, values, column_index, table, job_context, env):\n"
                    "    return {'values': list(values), 'warnings': []}\n"
                ),
            )
    return buffer.getvalue()


async def _create_config(
    async_client: AsyncClient,
    headers: dict[str, str],
    workspace_id: str,
) -> tuple[str, dict[str, Any]]:
    base = f"/api/v1/workspaces/{workspace_id}/configs"
    manifest = _manifest("Job Config", ["member_id", "name"])
    package_bytes = _package(manifest, "job-config")
    created = await async_client.post(
        base,
        headers=headers,
        data={
            "slug": "job-config",
            "title": "Job Config",
            "manifest_json": json.dumps(manifest),
        },
        files={"package": ("job-config.zip", package_bytes, "application/zip")},
    )
    created.raise_for_status()
    detail = created.json()
    version = detail["versions"][0]
    return version["config_version_id"], manifest


async def _upload_document(
    async_client: AsyncClient,
    headers: dict[str, str],
    workspace_id: str,
    workbook: Workbook,
    filename: str = "input.xlsx",
) -> str:
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        files={
            "file": (
                filename,
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    response.raise_for_status()
    return response.json()["document_id"]


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
    assert artifact_payload["config"]["config_version_id"] == version_id

    output = await async_client.get(f"{base}/{job_id}/output", headers=headers)
    output.raise_for_status()
    assert output.content
    assert output.headers["content-type"] in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }


async def test_job_submission_with_document_input(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    headers, workspace_id = await _auth(async_client, seed_identity)
    version_id, _ = await _create_config(async_client, headers, workspace_id)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["Member ID", "First Name"])
    sheet.append(["1001", "Alice"])
    document_id = await _upload_document(async_client, headers, workspace_id, workbook)

    jobs_endpoint = f"/api/v1/workspaces/{workspace_id}/jobs"
    payload = {"config_version_id": version_id, "document_ids": [document_id]}
    submitted = await async_client.post(jobs_endpoint, headers=headers, json=payload)
    assert submitted.status_code == 201, submitted.text
    job_payload = submitted.json()
    job_id = job_payload["job_id"]
    assert job_payload["status"] == "succeeded"
    assert job_payload["input_hash"]

    # Resubmitting with the same document should reuse the existing job based on the derived hash.
    resubmitted = await async_client.post(jobs_endpoint, headers=headers, json=payload)
    assert resubmitted.status_code == 201, resubmitted.text
    assert resubmitted.json()["job_id"] == job_id

    run_request = json.loads(Path(job_payload["run_request_uri"]).read_text(encoding="utf-8"))
    assert run_request["input_paths"]
    assert run_request["input_documents"]
    first_document = run_request["input_documents"][0]
    assert first_document["document_id"] == document_id
    assert first_document["filename"].startswith("input") or first_document["filename"].endswith(".xlsx")


async def test_job_submission_missing_document_id_returns_error(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    headers, workspace_id = await _auth(async_client, seed_identity)
    version_id, _ = await _create_config(async_client, headers, workspace_id)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/jobs",
        headers=headers,
        json={"config_version_id": version_id, "document_ids": ["nonexistent"]},
    )
    assert response.status_code == 400
    assert "Document" in response.text


async def test_job_submission_accepts_multiple_documents(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    headers, workspace_id = await _auth(async_client, seed_identity)
    version_id, _ = await _create_config(async_client, headers, workspace_id)

    workbook_a = Workbook()
    sheet_a = workbook_a.active
    sheet_a.append(["Member ID", "First Name"])
    sheet_a.append(["2001", "Bruno"])

    workbook_b = Workbook()
    sheet_b = workbook_b.active
    sheet_b.append(["Member ID", "First Name"])
    sheet_b.append(["2002", "Casey"])

    doc_a = await _upload_document(async_client, headers, workspace_id, workbook_a, filename="input-a.xlsx")
    doc_b = await _upload_document(async_client, headers, workspace_id, workbook_b, filename="input-b.xlsx")

    payload = {"config_version_id": version_id, "document_ids": [doc_a, doc_b]}
    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/jobs",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    run_request = json.loads(Path(response.json()["run_request_uri"]).read_text(encoding="utf-8"))
    assert len(run_request["input_paths"]) == 2
    document_ids = [doc["document_id"] for doc in run_request["input_documents"]]
    assert document_ids == [doc_a, doc_b]
