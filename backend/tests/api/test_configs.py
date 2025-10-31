"""Integration tests for config management and job orchestration."""

from __future__ import annotations

import io
import json
import textwrap
import zipfile
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook

from backend.app.features.configs.storage import ConfigStorage
from backend.app.features.configs.spec import ManifestLoader
from backend.app.shared.core.config import get_settings
from backend.tests.utils import login

pytestmark = pytest.mark.asyncio


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    settings = get_settings()
    token = client.cookies.get(settings.session_csrf_cookie_name)
    assert token, "CSRF cookie not present"
    return {"X-CSRF-Token": token}


def _column_script(field: str, *, include_transform: bool = True) -> str:
    body = f"""
    def detect_{field}(*, header, values_sample, column_index, table, job_context, env):
        return {{"scores": {{"{field}": 1.0}}}}
    """
    if include_transform:
        body += """

    def transform(*, header, values, column_index, table, job_context, env):
        return {"values": list(values), "warnings": []}
    """
    return textwrap.dedent(body).strip() + "\n"


def _build_manifest(sheet_title: str = "Members") -> tuple[dict[str, Any], dict[str, str]]:
    manifest: dict[str, Any] = {
        "config_script_api_version": "1",
        "info": {"schema": "ade.manifest/v1.0", "title": "QA Config", "version": "1.0.0"},
        "engine": {"writer": {"output_sheet": sheet_title}},
        "columns": {
            "order": ["member_id", "first_name", "legacy_code"],
            "meta": {
                "member_id": {
                    "label": "Member ID",
                    "required": True,
                    "enabled": True,
                    "script": "columns/member_id.py",
                },
                "first_name": {
                    "label": "First Name",
                    "required": False,
                    "enabled": True,
                    "script": "columns/first_name.py",
                },
                "legacy_code": {
                    "label": "Legacy Code",
                    "required": False,
                    "enabled": False,
                    "script": "columns/legacy_code.py",
                },
            },
        },
    }
    scripts = {
        "columns/member_id.py": _column_script("member_id"),
        "columns/first_name.py": _column_script("first_name"),
    }
    return manifest, scripts


def _build_package(manifest: dict[str, Any], scripts: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("columns/__init__.py", "")
        for path, content in scripts.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _config_endpoint(workspace_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/configs"


def _jobs_endpoint(workspace_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/jobs"


async def test_create_config_rejects_column_without_transform(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    await login(async_client, email=owner["email"], password=owner["password"])

    manifest, scripts = _build_manifest()
    scripts["columns/member_id.py"] = _column_script("member_id", include_transform=False)
    package_bytes = _build_package(manifest, scripts)

    slug = f"invalid-{uuid4().hex[:8]}"
    headers = _csrf_headers(async_client)
    response = await async_client.post(
        _config_endpoint(workspace_id),
        data={
            "slug": slug,
            "title": "Invalid Config",
            "manifest_json": json.dumps(manifest),
        },
        files={
            "package": ("package.zip", package_bytes, "application/zip"),
        },
        headers=headers,
    )

    assert response.status_code == 400
    detail = response.json().get("detail")
    assert isinstance(detail, dict)
    diagnostics = detail.get("diagnostics", [])
    assert any(item.get("code") == "column.transform.missing" for item in diagnostics)


async def test_create_config_stores_canonical_manifest_and_package_hashes(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    await login(async_client, email=owner["email"], password=owner["password"])

    manifest, scripts = _build_manifest(sheet_title="Audited")
    package_bytes = _build_package(manifest, scripts)

    slug = f"config-{uuid4().hex[:8]}"
    headers = _csrf_headers(async_client)
    response = await async_client.post(
        _config_endpoint(workspace_id),
        data={
            "slug": slug,
            "title": "Canonical Config",
            "description": "Smoke test",
            "manifest_json": json.dumps(manifest),
        },
        files={
            "package": ("package.zip", package_bytes, "application/zip"),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    assert payload.get("active_version") is None
    versions = payload.get("versions", [])
    assert len(versions) == 1
    version = versions[0]

    loader = ManifestLoader()
    canonical_manifest = loader.load(manifest).model_dump(mode="json")
    canonical_json = json.dumps(canonical_manifest, sort_keys=True, separators=(",", ":"))
    expected_manifest_hash = sha256(canonical_json.encode("utf-8")).hexdigest()
    assert version["manifest_sha256"] == expected_manifest_hash
    assert version["config_script_api_version"] == "1"

    package_path = Path(version["package_path"])
    assert package_path.exists()
    assert (package_path / "manifest.json").exists()

    sequence = int(version["sequence"])
    archive_path = package_path.parent / f"v{sequence:04d}.zip"
    assert archive_path.exists()

    storage = ConfigStorage(get_settings())
    expected_package_hash = storage.compute_package_hash(archive_path)
    assert version["package_sha256"] == expected_package_hash


async def test_job_artifact_reflects_manifest_columns(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    await login(async_client, email=owner["email"], password=owner["password"])

    manifest, scripts = _build_manifest(sheet_title="Members")
    package_bytes = _build_package(manifest, scripts)

    slug = f"job-{uuid4().hex[:8]}"
    headers = _csrf_headers(async_client)
    create_response = await async_client.post(
        _config_endpoint(workspace_id),
        data={
            "slug": slug,
            "title": "Job Config",
            "manifest_json": json.dumps(manifest),
        },
        files={
            "package": ("package.zip", package_bytes, "application/zip"),
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    config_payload = create_response.json()
    version_id = config_payload["versions"][0]["config_version_id"]

    job_response = await async_client.post(
        _jobs_endpoint(workspace_id),
        json={"config_version_id": version_id},
        headers=headers,
    )
    assert job_response.status_code == 201, job_response.text
    job_payload = job_response.json()
    assert job_payload["status"] == "succeeded"
    assert job_payload["attempt"] == 1
    assert job_payload["logs_uri"]
    assert job_payload["run_request_uri"]
    trace_id = job_payload["trace_id"]

    job_id = job_payload["job_id"]

    artifact_response = await async_client.get(
        f"{_jobs_endpoint(workspace_id)}/{job_id}/artifact"
    )
    assert artifact_response.status_code == 200
    artifact = artifact_response.json()
    assert artifact["job"]["trace_id"] == trace_id
    pass_names = [p["name"] for p in artifact["passes"]]
    assert pass_names == [
        "detect_tables",
        "map_columns",
        "transform_values",
        "validate_values",
        "generate_normalized_workbook",
    ]

    tables_pass = next(p for p in artifact["passes"] if p["name"] == "detect_tables")
    assert tables_pass["summary"]["tables"]

    mapping_pass = next(p for p in artifact["passes"] if p["name"] == "map_columns")
    assignments = mapping_pass["summary"]["assignments"]
    assert any(item["target_field"] == "member_id" for item in assignments)
    assert any(item["raw_header"] == "Legacy Code" for item in assignments)

    transform_pass = next(p for p in artifact["passes"] if p["name"] == "transform_values")
    transform_fields = {entry["field"] for entry in transform_pass["summary"]["fields"]}
    assert {"member_id", "first_name"}.issubset(transform_fields)

    validate_pass = next(p for p in artifact["passes"] if p["name"] == "validate_values")
    validate_fields = {entry["field"] for entry in validate_pass["summary"]["fields"]}
    assert {"member_id", "first_name"}.issubset(validate_fields)

    generate_pass = next(
        p for p in artifact["passes"] if p["name"] == "generate_normalized_workbook"
    )
    assert generate_pass["summary"]["sheet"] == "Members"
    assert generate_pass["summary"]["headers"] == ["Member ID", "First Name"]

    output_response = await async_client.get(
        f"{_jobs_endpoint(workspace_id)}/{job_id}/output"
    )
    assert (
        output_response.headers.get("content-type")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(io.BytesIO(output_response.content))
    sheet = workbook.active
    assert sheet.title == "Members"
    rows = list(sheet.iter_rows(values_only=True))
    assert rows == [("Member ID", "First Name")]

    # Inspect run request and logs
    run_request = json.loads(Path(job_payload["run_request_uri"]).read_text(encoding="utf-8"))
    assert run_request["schema"] == "ade.run_request/v1"
    assert run_request["job_id"] == job_id

    log_lines = [
        json.loads(line)
        for line in Path(job_payload["logs_uri"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(entry.get("event") == "worker.spawn" for entry in log_lines)
    exit_event = next(entry for entry in log_lines if entry.get("event") == "worker.exit")
    assert exit_event["status"] == "succeeded"
    assert exit_event["elapsed_ms"] >= 0


async def test_job_submission_idempotent_on_input_hash(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    await login(async_client, email=owner["email"], password=owner["password"])

    manifest, scripts = _build_manifest(sheet_title="Idempotent")
    package_bytes = _build_package(manifest, scripts)

    slug = f"idem-{uuid4().hex[:8]}"
    headers = _csrf_headers(async_client)
    create_response = await async_client.post(
        _config_endpoint(workspace_id),
        data={
            "slug": slug,
            "title": "Idempotent Config",
            "manifest_json": json.dumps(manifest),
        },
        files={
            "package": ("package.zip", package_bytes, "application/zip"),
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    version_id = create_response.json()["versions"][0]["config_version_id"]

    input_hash = "abc123"
    first = await async_client.post(
        _jobs_endpoint(workspace_id),
        json={"config_version_id": version_id, "input_hash": input_hash},
        headers=headers,
    )
    assert first.status_code == 201
    first_payload = first.json()

    second = await async_client.post(
        _jobs_endpoint(workspace_id),
        json={"config_version_id": version_id, "input_hash": input_hash},
        headers=headers,
    )
    assert second.status_code == 201
    second_payload = second.json()

    assert second_payload["job_id"] == first_payload["job_id"]
    assert second_payload["attempt"] == 1
    assert second_payload["status"] == "succeeded"


async def test_validate_endpoint_returns_diagnostics(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    await login(async_client, email=owner["email"], password=owner["password"])

    manifest, scripts = _build_manifest()
    scripts["columns/member_id.py"] = _column_script("member_id", include_transform=False)
    package_bytes = _build_package(manifest, scripts)

    headers = _csrf_headers(async_client)
    response = await async_client.post(
        f"{_config_endpoint(workspace_id)}/validate",
        data={"manifest_json": json.dumps(manifest)},
        files={"package": ("package.zip", package_bytes, "application/zip")},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    diagnostics = payload.get("diagnostics", [])
    assert any(diag["code"] == "column.transform.missing" for diag in diagnostics)
