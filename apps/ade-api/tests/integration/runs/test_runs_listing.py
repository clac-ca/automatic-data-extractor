import pytest

from ade_api.models import BuildStatus, ConfigurationStatus, RunStatus

from tests.integration.runs.helpers import (
    auth_headers,
    make_build,
    make_configuration,
    make_document,
    make_run,
)

pytestmark = pytest.mark.asyncio


async def test_workspace_run_listing_filters_by_status(
    async_client,
    seed_identity,
    session,
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
    session.add_all([configuration, other_configuration])
    await session.flush()

    build = make_build(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        status=BuildStatus.READY,
    )
    build_other = make_build(
        workspace_id=seed_identity.secondary_workspace_id,
        configuration_id=other_configuration.id,
        status=BuildStatus.READY,
        fingerprint="fingerprint-other",
    )
    document = make_document(workspace_id=workspace_id, filename="input.csv")
    document_other = make_document(
        workspace_id=seed_identity.secondary_workspace_id,
        filename="other.csv",
    )
    session.add_all([build, build_other, document, document_other])
    await session.flush()

    run_ok = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        build_id=build.id,
        document_id=document.id,
        status=RunStatus.SUCCEEDED,
    )
    run_failed = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        build_id=build.id,
        document_id=document.id,
        status=RunStatus.FAILED,
    )
    run_other_workspace = make_run(
        workspace_id=seed_identity.secondary_workspace_id,
        configuration_id=other_configuration.id,
        build_id=build_other.id,
        document_id=document_other.id,
        status=RunStatus.SUCCEEDED,
    )
    session.add_all([run_ok, run_failed, run_other_workspace])
    await session.commit()

    headers = await auth_headers(async_client, seed_identity.workspace_owner)

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
