import anyio
import json
import pytest

from ade_api.models import ConfigurationStatus, RunStatus

from tests.integration.runs.helpers import (
    auth_headers,
    make_configuration,
    make_document,
    make_run,
)

pytestmark = pytest.mark.asyncio


async def test_workspace_run_listing_filters_by_status(
    async_client,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="Runs Config",
        status=ConfigurationStatus.ACTIVE,
    )
    other_configuration = make_configuration(
        workspace_id=workspace_id,
        name="Other Config",
        status=ConfigurationStatus.DRAFT,
    )
    db_session.add_all([configuration, other_configuration])
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    document_other = make_document(
        workspace_id=seed_identity.secondary_workspace_id,
        filename="other.csv",
    )
    db_session.add_all([document, document_other])
    await anyio.to_thread.run_sync(db_session.flush)

    run_ok = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.SUCCEEDED,
    )
    run_failed = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.FAILED,
    )
    run_other_workspace = make_run(
        workspace_id=seed_identity.secondary_workspace_id,
        configuration_id=other_configuration.id,
        file_version_id=document_other.current_version_id,
        status=RunStatus.SUCCEEDED,
    )
    db_session.add_all([run_ok, run_failed, run_other_workspace])
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)

    all_runs = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        params={"includeTotal": "true"},
    )
    assert all_runs.status_code == 200
    payload = all_runs.json()
    assert payload["meta"]["totalIncluded"] is True
    assert payload["meta"]["totalCount"] == 2

    status_filters = json.dumps(
        [{"id": "status", "operator": "eq", "value": RunStatus.SUCCEEDED.value}]
    )
    filtered = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        params={"filters": status_filters, "includeTotal": "true"},
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["meta"]["totalIncluded"] is True
    assert filtered_payload["meta"]["totalCount"] == 1
    assert filtered_payload["items"][0]["id"] == str(run_ok.id)
