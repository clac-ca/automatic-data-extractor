import io

import anyio
import pytest

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.settings import Settings
from ade_db.models import File, FileKind, FileVersion, FileVersionOrigin, RunStatus
from ade_storage import build_storage_adapter
from tests.api.integration.runs.helpers import (
    auth_headers,
    make_configuration,
    make_document,
    make_run,
)

pytestmark = pytest.mark.asyncio


async def test_run_output_endpoint_serves_file(
    async_client,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="Output Config",
    )
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    db_session.add_all([document])
    await anyio.to_thread.run_sync(db_session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.SUCCEEDED,
    )
    run.completed_at = utc_now()
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.flush)

    output_file_id = generate_uuid7()
    output_blob_name = f"{workspace_id}/files/{output_file_id}"
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

    storage = build_storage_adapter(settings)
    stored = storage.write(output_blob_name, io.BytesIO(b"demo-output"))

    output_version = FileVersion(
        id=generate_uuid7(),
        file_id=output_file_id,
        version_no=1,
        origin=FileVersionOrigin.GENERATED,
        run_id=run.id,
        created_by_user_id=None,
        sha256=stored.sha256,
        byte_size=stored.byte_size,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename_at_upload="normalized.xlsx",
        storage_version_id=stored.version_id or stored.sha256,
    )
    output_file.current_version = output_version
    output_file.versions.append(output_version)
    db_session.add_all([output_file, output_version])
    await anyio.to_thread.run_sync(db_session.flush)
    run.output_file_version_id = output_version.id
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)

    metadata = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/output",
        headers=headers,
    )
    assert metadata.status_code == 200
    payload = metadata.json()
    assert payload["has_output"] is True
    assert payload["ready"] is True
    assert payload["filename"] == "normalized.xlsx"
    assert payload["fileVersionId"] == str(output_version.id)
    assert payload["download_url"].endswith(
        f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/output/download"
    )

    download = await async_client.get(payload["download_url"], headers=headers)
    assert download.status_code == 200
    assert download.text == "demo-output"
