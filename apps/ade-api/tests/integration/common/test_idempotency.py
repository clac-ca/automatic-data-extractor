from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from ade_api.infra.storage import workspace_config_root
from ade_api.models import Run
from tests.integration.runs.helpers import auth_headers, make_configuration, make_document

pytestmark = pytest.mark.asyncio


async def test_idempotency_replays_and_conflicts(
    async_client,
    seed_identity,
    session,
    settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="Idempotency Config",
    )
    session.add(configuration)
    session.flush()

    config_dir = workspace_config_root(settings, workspace_id, configuration.id)
    config_dir.mkdir(parents=True, exist_ok=True)

    document_one = make_document(workspace_id=workspace_id, filename="idempotency-one.csv")
    document_two = make_document(workspace_id=workspace_id, filename="idempotency-two.csv")
    session.add_all([document_one, document_two])
    session.commit()

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    idempotency_key = f"idem-{uuid4().hex}"

    payload_one = {
        "input_document_id": str(document_one.id),
        "configuration_id": str(configuration.id),
        "options": {"log_level": "INFO"},
    }
    response_one = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json=payload_one,
    )
    assert response_one.status_code == 201, response_one.text
    run_id = response_one.json()["id"]

    response_two = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json=payload_one,
    )
    assert response_two.status_code == 201, response_two.text
    assert response_two.json()["id"] == run_id

    result = session.execute(
        select(Run).where(
            Run.configuration_id == configuration.id,
            Run.input_document_id == document_one.id,
        )
    )
    runs = list(result.scalars())
    assert len(runs) == 1
    assert runs[0].id == UUID(run_id)

    conflict_payload = {
        "input_document_id": str(document_two.id),
        "configuration_id": str(configuration.id),
        "options": {"log_level": "INFO"},
    }
    conflict = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json=conflict_payload,
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["type"] == "idempotency_key_conflict"

    missing = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        json=payload_one,
    )
    assert missing.status_code == 422, missing.text
    assert missing.json()["type"] == "validation_error"
