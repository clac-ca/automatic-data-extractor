from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select
from httpx import AsyncClient

from ade_api.common.time import utc_now
from ade_api.db.mixins import generate_uuid7
from ade_api.infra.storage import workspace_config_root, workspace_run_root
from ade_api.models import (
    Build,
    BuildStatus,
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentSource,
    DocumentStatus,
    Run,
    RunStatus,
)
from ade_api.settings import Settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def _auth_headers(client: AsyncClient, account) -> dict[str, str]:
    token, _ = await login(client, email=account.email, password=account.password)
    return {"Authorization": f"Bearer {token}"}


async def test_workspace_run_listing_filters_by_status(
    async_client: AsyncClient,
    seed_identity,
    session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Runs Config",
        status=ConfigurationStatus.ACTIVE,
    )
    other_configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Other Config",
        status=ConfigurationStatus.DRAFT,
    )
    session.add_all([configuration, other_configuration])
    await session.flush()

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        fingerprint="fingerprint",
        status=BuildStatus.READY,
        created_at=utc_now(),
    )
    build_other = Build(
        id=generate_uuid7(),
        workspace_id=seed_identity.secondary_workspace_id,
        configuration_id=other_configuration.id,
        fingerprint="fingerprint-other",
        status=BuildStatus.READY,
        created_at=utc_now(),
    )
    document = Document(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=12,
        sha256="deadbeef",
        stored_uri="documents/input.csv",
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    document_other = Document(
        id=generate_uuid7(),
        workspace_id=seed_identity.secondary_workspace_id,
        original_filename="other.csv",
        content_type="text/csv",
        byte_size=12,
        sha256="deadbeef",
        stored_uri="documents/other.csv",
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add_all([build, build_other, document, document_other])
    await session.flush()

    run_ok = Run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        build_id=build.id,
        input_document_id=document.id,
        status=RunStatus.SUCCEEDED,
        created_at=utc_now(),
    )
    run_failed = Run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        build_id=build.id,
        input_document_id=document.id,
        status=RunStatus.FAILED,
        created_at=utc_now(),
    )
    run_other_workspace = Run(
        workspace_id=seed_identity.secondary_workspace_id,
        configuration_id=other_configuration.id,
        build_id=build_other.id,
        input_document_id=document_other.id,
        status=RunStatus.SUCCEEDED,
        created_at=utc_now(),
    )
    session.add_all([run_ok, run_failed, run_other_workspace])
    await session.commit()

    headers = await _auth_headers(async_client, seed_identity.workspace_owner)

    all_runs = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        params={"include_total": "true"},
    )
    assert all_runs.status_code == 200
    payload = all_runs.json()
    assert payload["total"] == 2

    filtered = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        params={"status": RunStatus.SUCCEEDED.value, "include_total": "true"},
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["id"] == str(run_ok.id)


async def test_run_output_endpoint_serves_file(
    async_client: AsyncClient,
    seed_identity,
    session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Output Config",
        status=ConfigurationStatus.ACTIVE,
    )
    session.add(configuration)
    await session.flush()

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        fingerprint="fingerprint",
        status=BuildStatus.READY,
        created_at=utc_now(),
    )
    document = Document(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=12,
        sha256="deadbeef",
        stored_uri="documents/input.csv",
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add_all([build, document])
    await session.flush()

    run = Run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        build_id=build.id,
        input_document_id=document.id,
        status=RunStatus.SUCCEEDED,
        created_at=utc_now(),
        finished_at=utc_now(),
    )
    session.add(run)
    await session.commit()

    run_dir = workspace_run_root(settings, workspace_id, run.id)
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "normalized.xlsx"
    output_file.write_text("demo-output", encoding="utf-8")

    headers = await _auth_headers(async_client, seed_identity.workspace_owner)

    metadata = await async_client.get(f"/api/v1/runs/{run.id}/output", headers=headers)
    assert metadata.status_code == 200
    payload = metadata.json()
    assert payload["has_output"] is True
    assert payload["ready"] is True
    assert payload["output_path"] == "output/normalized.xlsx"
    assert payload["download_url"].endswith(f"/api/v1/runs/{run.id}/output/download")

    download = await async_client.get(payload["download_url"], headers=headers)
    assert download.status_code == 200
    assert download.text == "demo-output"


async def test_create_runs_batch_creates_runs(
    async_client: AsyncClient,
    seed_identity,
    session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Batch Config",
        status=ConfigurationStatus.ACTIVE,
    )
    session.add(configuration)
    await session.flush()

    config_dir = workspace_config_root(settings, workspace_id, configuration.id)
    config_dir.mkdir(parents=True, exist_ok=True)

    documents = [
        Document(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            original_filename="input-a.csv",
            content_type="text/csv",
            byte_size=12,
            sha256="deadbeef",
            stored_uri="documents/input-a.csv",
            attributes={},
            status=DocumentStatus.UPLOADED,
            source=DocumentSource.MANUAL_UPLOAD,
            expires_at=utc_now(),
        ),
        Document(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            original_filename="input-b.csv",
            content_type="text/csv",
            byte_size=14,
            sha256="deadbeef",
            stored_uri="documents/input-b.csv",
            attributes={},
            status=DocumentStatus.UPLOADED,
            source=DocumentSource.MANUAL_UPLOAD,
            expires_at=utc_now(),
        ),
    ]
    session.add_all(documents)
    await session.commit()

    headers = await _auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.post(
        f"/api/v1/configurations/{configuration.id}/runs/batch",
        headers=headers,
        json={
            "document_ids": [str(doc.id) for doc in documents],
            "options": {"log_level": "INFO"},
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    runs = payload.get("runs", [])
    assert len(runs) == 2

    run_ids = [UUID(item["id"]) for item in runs]
    result = await session.execute(select(Run).where(Run.id.in_(run_ids)))
    stored = list(result.scalars())
    assert len(stored) == 2
    assert {run.input_document_id for run in stored} == {doc.id for doc in documents}
    assert all(run.input_sheet_names is None for run in stored)


async def test_create_runs_batch_queue_full_all_or_nothing(
    async_client: AsyncClient,
    seed_identity,
    session,
    override_app_settings,
) -> None:
    updated_settings = override_app_settings(queue_size=1)
    workspace_id = seed_identity.workspace_id
    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Batch Config",
        status=ConfigurationStatus.ACTIVE,
    )
    session.add(configuration)
    await session.flush()

    config_dir = workspace_config_root(updated_settings, workspace_id, configuration.id)
    config_dir.mkdir(parents=True, exist_ok=True)

    documents = [
        Document(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            original_filename="input-a.csv",
            content_type="text/csv",
            byte_size=12,
            sha256="deadbeef",
            stored_uri="documents/input-a.csv",
            attributes={},
            status=DocumentStatus.UPLOADED,
            source=DocumentSource.MANUAL_UPLOAD,
            expires_at=utc_now(),
        ),
        Document(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            original_filename="input-b.csv",
            content_type="text/csv",
            byte_size=14,
            sha256="deadbeef",
            stored_uri="documents/input-b.csv",
            attributes={},
            status=DocumentStatus.UPLOADED,
            source=DocumentSource.MANUAL_UPLOAD,
            expires_at=utc_now(),
        ),
    ]
    session.add_all(documents)
    await session.commit()

    headers = await _auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.post(
        f"/api/v1/configurations/{configuration.id}/runs/batch",
        headers=headers,
        json={
            "document_ids": [str(doc.id) for doc in documents],
            "options": {"log_level": "INFO"},
        },
    )

    assert response.status_code == 429, response.text
    assert response.json()["detail"]["error"]["code"] == "run_queue_full"
    result = await session.execute(select(Run).where(Run.configuration_id == configuration.id))
    assert result.scalars().all() == []
