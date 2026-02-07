from __future__ import annotations

import anyio
import io

import pytest

from ade_api.common.time import utc_now
from ade_storage import build_storage_adapter
from ade_db.models import RunStatus
from ade_api.settings import Settings

from tests.api.integration.runs.helpers import auth_headers, make_configuration, make_document, make_run

pytestmark = pytest.mark.asyncio


async def test_run_events_stream_endpoint_returns_live_sse(
    async_client,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="SSE Config",
    )
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    db_session.add(document)
    await anyio.to_thread.run_sync(db_session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.SUCCEEDED,
    )
    run.completed_at = utc_now()
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    events_blob_name = f"{workspace_id}/runs/{run.id}/logs/events.ndjson"
    events_payload = (
        '{"timestamp":"2026-01-01T00:00:00Z","event":"run.start","message":"start","data":{}}\n'
        '{"timestamp":"2026-01-01T00:00:01Z","event":"run.complete","message":"done","data":{"status":"succeeded"}}\n'
    ).encode("utf-8")
    storage = build_storage_adapter(settings)
    storage.write(events_blob_name, io.BytesIO(events_payload))

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    async with async_client.stream(
        "GET",
        f"/api/v1/runs/{run.id}/events/stream",
        headers=headers,
    ) as response:
        assert response.status_code == 200
        lines: list[str] = []
        async for line in response.aiter_lines():
            if not line:
                continue
            lines.append(line)
            if line == "event: run.complete":
                break

    joined = "\n".join(lines)
    assert "event: run.start" in joined
    assert "event: run.complete" in joined
    assert "id: " in joined


async def test_run_events_stream_endpoint_honors_cursor_offset(
    async_client,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="SSE Cursor Config",
    )
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="input.csv")
    db_session.add(document)
    await anyio.to_thread.run_sync(db_session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.SUCCEEDED,
    )
    run.completed_at = utc_now()
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    first_line = '{"timestamp":"2026-01-01T00:00:00Z","event":"run.start","message":"start","data":{}}\n'
    second_line = (
        '{"timestamp":"2026-01-01T00:00:01Z","event":"run.complete","message":"done",'
        '"data":{"status":"succeeded"}}\n'
    )
    events_payload = (first_line + second_line).encode("utf-8")
    cursor_offset = len(first_line.encode("utf-8"))

    events_blob_name = f"{workspace_id}/runs/{run.id}/logs/events.ndjson"
    storage = build_storage_adapter(settings)
    storage.write(events_blob_name, io.BytesIO(events_payload))

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    async with async_client.stream(
        "GET",
        f"/api/v1/runs/{run.id}/events/stream",
        headers=headers,
        params={"cursor": cursor_offset},
    ) as response:
        assert response.status_code == 200
        lines: list[str] = []
        async for line in response.aiter_lines():
            if not line:
                continue
            lines.append(line)
            if line == "event: run.complete":
                break

    joined = "\n".join(lines)
    assert "event: run.start" not in joined
    assert "event: run.complete" in joined


async def test_run_events_stream_endpoint_exits_for_cancelled_run_without_logs(
    async_client,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="SSE Cancelled Config",
    )
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
    run.completed_at = utc_now()
    run.error_message = "Run cancelled by user"
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    with anyio.fail_after(5):
        async with async_client.stream(
            "GET",
            f"/api/v1/runs/{run.id}/events/stream",
            headers=headers,
        ) as response:
            assert response.status_code == 200
            lines = [line async for line in response.aiter_lines() if line]

    assert lines == []
