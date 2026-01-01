from uuid import UUID

import pytest
from sqlalchemy import select
from ade_api.infra.storage import workspace_config_root
from ade_api.models import Run

from tests.integration.runs.helpers import auth_headers, make_configuration, make_document

pytestmark = pytest.mark.asyncio


async def test_create_runs_batch_creates_runs(
    async_client,
    seed_identity,
    session,
    settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="Batch Config",
    )
    session.add(configuration)
    await session.flush()

    config_dir = workspace_config_root(settings, workspace_id, configuration.id)
    config_dir.mkdir(parents=True, exist_ok=True)

    documents = [
        make_document(workspace_id=workspace_id, filename="input-a.csv"),
        make_document(workspace_id=workspace_id, filename="input-b.csv", byte_size=14),
    ]
    session.add_all(documents)
    await session.commit()

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
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
    async_client,
    seed_identity,
    session,
    override_app_settings,
) -> None:
    updated_settings = override_app_settings(queue_size=1)
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="Batch Config",
    )
    session.add(configuration)
    await session.flush()

    config_dir = workspace_config_root(updated_settings, workspace_id, configuration.id)
    config_dir.mkdir(parents=True, exist_ok=True)

    documents = [
        make_document(workspace_id=workspace_id, filename="input-a.csv"),
        make_document(workspace_id=workspace_id, filename="input-b.csv", byte_size=14),
    ]
    session.add_all(documents)
    await session.commit()

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.post(
        f"/api/v1/configurations/{configuration.id}/runs/batch",
        headers=headers,
        json={
            "document_ids": [str(doc.id) for doc in documents],
            "options": {"log_level": "INFO"},
        },
    )

    assert response.status_code == 429, response.text
    payload = response.json()
    assert payload["type"] == "rate_limited"
    assert any(item.get("code") == "run_queue_full" for item in payload.get("errors", []))
    result = await session.execute(select(Run).where(Run.configuration_id == configuration.id))
    assert result.scalars().all() == []
