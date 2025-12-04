from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from ade_api.common.time import utc_now
from ade_api.core.models import Configuration, ConfigurationStatus, Run, RunStatus
from ade_api.infra.storage import workspace_run_root
from ade_api.settings import get_settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def _auth_headers(client: AsyncClient, account: dict[str, Any]) -> dict[str, str]:
    token, _ = await login(client, email=account["email"], password=account["password"])
    return {"Authorization": f"Bearer {token}"}


async def test_workspace_run_listing_filters_by_status(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    session,
) -> None:
    workspace_id = seed_identity["workspace_id"]
    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Runs Config",
        status=ConfigurationStatus.ACTIVE,
    )
    other_configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Other Config",
        status=ConfigurationStatus.ACTIVE,
    )
    session.add_all([configuration, other_configuration])
    await session.flush()

    run_ok = Run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        status=RunStatus.SUCCEEDED,
        created_at=utc_now(),
    )
    run_failed = Run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        status=RunStatus.FAILED,
        created_at=utc_now(),
    )
    run_other_workspace = Run(
        workspace_id=seed_identity["secondary_workspace_id"],
        configuration_id=other_configuration.id,
        status=RunStatus.SUCCEEDED,
        created_at=utc_now(),
    )
    session.add_all([run_ok, run_failed, run_other_workspace])
    await session.commit()

    headers = await _auth_headers(async_client, seed_identity["workspace_owner"])

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


async def test_run_outputs_endpoint_serves_files(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    session,
) -> None:
    settings = get_settings()
    workspace_id = seed_identity["workspace_id"]
    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Output Config",
        status=ConfigurationStatus.ACTIVE,
    )
    session.add(configuration)
    await session.flush()

    run = Run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
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

    headers = await _auth_headers(async_client, seed_identity["workspace_owner"])

    listing = await async_client.get(f"/api/v1/runs/{run.id}/outputs", headers=headers)
    assert listing.status_code == 200
    listing_payload = listing.json()
    assert listing_payload["files"]
    assert listing_payload["files"][0]["name"] == "normalized.xlsx"

    download = await async_client.get(listing_payload["files"][0]["download_url"], headers=headers)
    assert download.status_code == 200
    assert download.text == "demo-output"
