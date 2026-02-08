from uuid import UUID

import anyio
import pytest
from sqlalchemy import select

from ade_db.models import Run
from ade_storage import workspace_config_root
from tests.api.integration.runs.helpers import auth_headers, make_configuration, make_document

pytestmark = pytest.mark.asyncio


async def test_create_runs_batch_creates_runs(
    async_client,
    seed_identity,
    db_session,
    settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="Batch Config",
    )
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    config_dir = workspace_config_root(settings, workspace_id, configuration.id)
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "pyproject.toml").write_text(
        (
            "[project]\n"
            "name = \"ade-config\"\n"
            "version = \"0.0.0\"\n"
            "dependencies = [\"ade-engine\"]\n"
        ),
        encoding="utf-8",
    )

    documents = [
        make_document(workspace_id=workspace_id, filename="input-a.csv"),
        make_document(workspace_id=workspace_id, filename="input-b.csv", byte_size=14),
    ]
    db_session.add_all(documents)
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs/batch",
        headers=headers,
        json={
            "document_ids": [str(doc.id) for doc in documents],
            "configuration_id": str(configuration.id),
            "options": {"log_level": "INFO"},
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    runs = payload.get("runs", [])
    assert len(runs) == 2

    run_ids = [UUID(item["id"]) for item in runs]

    def _load_runs():
        result = db_session.execute(select(Run).where(Run.id.in_(run_ids)))
        return list(result.scalars())

    stored = await anyio.to_thread.run_sync(_load_runs)
    assert len(stored) == 2
    assert {run.input_file_version_id for run in stored} == {
        doc.current_version_id for doc in documents
    }
    assert all(run.input_sheet_names is None for run in stored)
