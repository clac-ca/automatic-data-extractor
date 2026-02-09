"""Document download error handling tests."""

from __future__ import annotations

import io
from uuid import UUID

import anyio
import pytest
from httpx import AsyncClient

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_storage import build_storage_adapter
from ade_db.models import File, FileKind, FileVersion, FileVersionOrigin
from ade_api.settings import Settings
from tests.api.utils import login
from .helpers import seed_failed_run

pytestmark = pytest.mark.asyncio


def _create_output_version(
    *,
    db_session,
    settings: Settings,
    workspace_id: UUID,
    document: File,
    payload: bytes,
    filename: str = "normalized.xlsx",
) -> FileVersion:
    output_file_id = generate_uuid7()
    output_blob_name = f"{workspace_id}/files/{output_file_id}"

    storage = build_storage_adapter(settings)
    stored = storage.write(output_blob_name, io.BytesIO(payload))

    output_file = File(
        id=output_file_id,
        workspace_id=workspace_id,
        kind=FileKind.OUTPUT,
        name=f"{document.name} (Output)",
        name_key=f"output:{document.id}",
        blob_name=output_blob_name,
        source_file_id=document.id,
        attributes={},
        uploaded_by_user_id=None,
        comment_count=0,
    )
    output_version = FileVersion(
        id=generate_uuid7(),
        file_id=output_file_id,
        version_no=1,
        origin=FileVersionOrigin.GENERATED,
        run_id=None,
        created_by_user_id=None,
        sha256=stored.sha256,
        byte_size=stored.byte_size,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename_at_upload=filename,
        storage_version_id=stored.version_id,
        created_at=utc_now(),
    )
    output_file.current_version = output_version
    output_file.versions.append(output_version)
    db_session.add_all([output_file, output_version])
    db_session.flush()
    return output_version


async def test_download_missing_file_returns_404(
    async_client: AsyncClient,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    """Downloading a document with a missing backing file should 404."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("missing.txt", b"payload", "text/plain")},
    )
    payload = upload.json()
    document_id = payload["id"]

    row = await anyio.to_thread.run_sync(db_session.get, File, UUID(document_id))
    assert row is not None
    storage = build_storage_adapter(settings)
    storage.delete(row.blob_name)

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download",
        headers=headers,
    )
    assert download.status_code == 404
    assert "was not found" in download.text


async def test_unified_download_returns_original_when_no_output_exists(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("source.csv", b"original-bytes", "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == b"original-bytes"
    assert 'filename="source.csv"' in download.headers["content-disposition"]


async def test_unified_download_prefers_newer_output_version(
    async_client: AsyncClient,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_id = seed_identity.workspace_id
    workspace_base = f"/api/v1/workspaces/{workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("source.csv", b"original-bytes", "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])
    document = await anyio.to_thread.run_sync(db_session.get, File, document_id)
    assert document is not None

    _create_output_version(
        db_session=db_session,
        settings=settings,
        workspace_id=workspace_id,
        document=document,
        payload=b"normalized-bytes",
    )
    await anyio.to_thread.run_sync(db_session.commit)

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == b"normalized-bytes"
    assert 'filename="normalized.xlsx"' in download.headers["content-disposition"]


async def test_unified_download_prefers_newer_input_version(
    async_client: AsyncClient,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_id = seed_identity.workspace_id
    workspace_base = f"/api/v1/workspaces/{workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("source.csv", b"original-v1", "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])
    document = await anyio.to_thread.run_sync(db_session.get, File, document_id)
    assert document is not None

    _create_output_version(
        db_session=db_session,
        settings=settings,
        workspace_id=workspace_id,
        document=document,
        payload=b"normalized-v1",
    )
    await anyio.to_thread.run_sync(db_session.commit)

    upload_newer_input = await async_client.post(
        f"{workspace_base}/documents/{document_id}/versions",
        headers=headers,
        files={"file": ("source.csv", b"original-v2", "text/csv")},
    )
    assert upload_newer_input.status_code == 201, upload_newer_input.text

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == b"original-v2"
    assert 'filename="source.csv"' in download.headers["content-disposition"]


async def test_unified_download_still_returns_output_after_failed_run_without_newer_artifact(
    async_client: AsyncClient,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_id = seed_identity.workspace_id
    workspace_base = f"/api/v1/workspaces/{workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("source.csv", b"original-v1", "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    document_id = UUID(upload.json()["id"])
    document = await anyio.to_thread.run_sync(db_session.get, File, document_id)
    assert document is not None

    _create_output_version(
        db_session=db_session,
        settings=settings,
        workspace_id=workspace_id,
        document=document,
        payload=b"normalized-v1",
    )
    await seed_failed_run(
        db_session,
        workspace_id=workspace_id,
        document_id=document_id,
        uploader_id=seed_identity.member.id,
    )
    await anyio.to_thread.run_sync(db_session.commit)

    download = await async_client.get(
        f"{workspace_base}/documents/{document_id}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == b"normalized-v1"
    assert 'filename="normalized.xlsx"' in download.headers["content-disposition"]


async def test_download_original_endpoint_returns_version_one(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    headers = {"X-API-Key": token}

    upload = await async_client.post(
        f"{workspace_base}/documents",
        headers=headers,
        files={"file": ("source.csv", b"original-v1", "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    upload_newer_input = await async_client.post(
        f"{workspace_base}/documents/{document_id}/versions",
        headers=headers,
        files={"file": ("source.csv", b"original-v2", "text/csv")},
    )
    assert upload_newer_input.status_code == 201, upload_newer_input.text

    download_original = await async_client.get(
        f"{workspace_base}/documents/{document_id}/original/download",
        headers=headers,
    )
    assert download_original.status_code == 200
    expected_payload = (
        b"original-v2" if settings.blob_versioning_mode == "off" else b"original-v1"
    )
    assert download_original.content == expected_payload
    assert 'filename="source.csv"' in download_original.headers["content-disposition"]
