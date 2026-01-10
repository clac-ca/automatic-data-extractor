import anyio
import pytest

from ade_api.common.time import utc_now
from ade_api.infra.storage import workspace_run_root
from ade_api.models import RunStatus
from ade_api.settings import Settings

from tests.integration.runs.helpers import auth_headers, make_configuration, make_document, make_run

pytestmark = pytest.mark.asyncio


async def test_run_output_endpoint_serves_file(
    async_client,
    seed_identity,
    session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="Output Config",
    )
    session.add(configuration)
    await anyio.to_thread.run_sync(session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    session.add_all([document])
    await anyio.to_thread.run_sync(session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        document_id=document.id,
        status=RunStatus.SUCCEEDED,
    )
    run.completed_at = utc_now()
    session.add(run)
    await anyio.to_thread.run_sync(session.commit)

    run_dir = workspace_run_root(settings, workspace_id, run.id)
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "normalized.xlsx"
    output_file.write_text("demo-output", encoding="utf-8")

    headers = await auth_headers(async_client, seed_identity.workspace_owner)

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
