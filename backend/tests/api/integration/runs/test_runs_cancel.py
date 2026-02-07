from __future__ import annotations

import anyio
import pytest
from sqlalchemy import select

from ade_db.models import Run, RunStatus

from tests.api.integration.runs.helpers import (
    auth_headers,
    make_configuration,
    make_document,
    make_run,
)

pytestmark = pytest.mark.asyncio


async def test_cancel_queued_run(
    async_client,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(workspace_id=workspace_id, name="Runs Config")
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    db_session.add(document)
    await anyio.to_thread.run_sync(db_session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.QUEUED,
    )
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.post(
        f"/api/v1/runs/{run.id}/cancel",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == str(run.id)
    assert payload["status"] == "cancelled"

    refreshed = await anyio.to_thread.run_sync(
        lambda: db_session.execute(
            select(Run)
            .where(Run.id == run.id)
            .execution_options(populate_existing=True)
        ).scalar_one()
    )
    assert refreshed.status is RunStatus.CANCELLED
    assert refreshed.completed_at is not None
    assert refreshed.claimed_by is None
    assert refreshed.claim_expires_at is None
    assert refreshed.error_message == "Run cancelled by user"


async def test_cancel_running_run(
    async_client,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(workspace_id=workspace_id, name="Runs Config")
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    db_session.add(document)
    await anyio.to_thread.run_sync(db_session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.RUNNING,
    )
    run.claimed_by = "worker-1"
    run.claim_expires_at = run.created_at
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.post(
        f"/api/v1/runs/{run.id}/cancel",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "cancelled"

    refreshed = await anyio.to_thread.run_sync(
        lambda: db_session.execute(
            select(Run)
            .where(Run.id == run.id)
            .execution_options(populate_existing=True)
        ).scalar_one()
    )
    assert refreshed.status is RunStatus.CANCELLED
    assert refreshed.completed_at is not None
    assert refreshed.claimed_by is None
    assert refreshed.claim_expires_at is None
    assert refreshed.error_message == "Run cancelled by user"


@pytest.mark.parametrize("status", [RunStatus.SUCCEEDED, RunStatus.FAILED])
async def test_cancel_terminal_run_conflicts(
    async_client,
    seed_identity,
    db_session,
    status: RunStatus,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(workspace_id=workspace_id, name="Runs Config")
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    db_session.add(document)
    await anyio.to_thread.run_sync(db_session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=status,
    )
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.post(
        f"/api/v1/runs/{run.id}/cancel",
        headers=headers,
    )
    assert response.status_code == 409, response.text


async def test_cancel_already_cancelled_is_idempotent(
    async_client,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(workspace_id=workspace_id, name="Runs Config")
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    db_session.add(document)
    await anyio.to_thread.run_sync(db_session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.CANCELLED,
    )
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.post(
        f"/api/v1/runs/{run.id}/cancel",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "cancelled"
