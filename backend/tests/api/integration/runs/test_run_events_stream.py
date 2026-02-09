from __future__ import annotations

import io
from datetime import UTC, datetime

import anyio
import pytest

from ade_api.common.time import utc_now
from ade_api.settings import Settings
from ade_db.models import Run, RunStatus
from ade_storage import build_storage_adapter
from tests.api.integration.runs.helpers import (
    auth_headers,
    make_configuration,
    make_document,
    make_run,
)

pytestmark = pytest.mark.asyncio


def _join_non_empty(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line)


async def test_run_events_stream_endpoint_returns_ready_message_and_end(
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
        b'{"timestamp":"2026-01-01T00:00:00Z","event":"run.start","message":"start","data":{}}\n'
        b'{"timestamp":"2026-01-01T00:00:01Z","event":"run.complete","message":"done","data":{"status":"succeeded"}}\n'
    )
    storage = build_storage_adapter(settings)
    storage.write(events_blob_name, io.BytesIO(events_payload))

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    with anyio.fail_after(5):
        async with async_client.stream(
            "GET",
            f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/events/stream",
            headers=headers,
        ) as response:
            assert response.status_code == 200
            lines = [line async for line in response.aiter_lines() if line]

    joined = _join_non_empty(lines)
    assert "event: ready" in joined
    assert "event: message" in joined
    assert "event: end" in joined
    assert "event: run.start" not in joined
    assert '"event":"run.start"' in joined
    assert '"reason":"run_complete"' in joined


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

    first_line = (
        '{"timestamp":"2026-01-01T00:00:00Z","event":"run.start",'
        '"message":"start","data":{}}\n'
    )
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
    with anyio.fail_after(5):
        async with async_client.stream(
            "GET",
            f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/events/stream",
            headers=headers,
            params={"cursor": cursor_offset},
        ) as response:
            assert response.status_code == 200
            lines = [line async for line in response.aiter_lines() if line]

    joined = _join_non_empty(lines)
    assert "event: ready" in joined
    assert '"event":"run.start"' not in joined
    assert '"event":"run.complete"' in joined


async def test_run_events_stream_endpoint_prefers_last_event_id_over_query_cursor(
    async_client,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="SSE Header Cursor Config",
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

    first_line = (
        '{"timestamp":"2026-01-01T00:00:00Z","event":"run.start",'
        '"message":"start","data":{}}\n'
    )
    second_line = (
        '{"timestamp":"2026-01-01T00:00:01Z","event":"run.complete","message":"done",'
        '"data":{"status":"succeeded"}}\n'
    )
    events_payload = (first_line + second_line).encode("utf-8")
    header_cursor = len(first_line.encode("utf-8"))

    events_blob_name = f"{workspace_id}/runs/{run.id}/logs/events.ndjson"
    storage = build_storage_adapter(settings)
    storage.write(events_blob_name, io.BytesIO(events_payload))

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    headers["Last-Event-ID"] = str(header_cursor)

    with anyio.fail_after(5):
        async with async_client.stream(
            "GET",
            f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/events/stream",
            headers=headers,
            params={"cursor": 0},
        ) as response:
            assert response.status_code == 200
            lines = [line async for line in response.aiter_lines() if line]

    joined = _join_non_empty(lines)
    assert '"event":"run.start"' not in joined
    assert '"event":"run.complete"' in joined


async def test_run_events_stream_endpoint_emits_terminal_end_for_cancelled_run_without_logs(
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
    with anyio.fail_after(10):
        async with async_client.stream(
            "GET",
            f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/events/stream",
            headers=headers,
        ) as response:
            assert response.status_code == 200
            lines = [line async for line in response.aiter_lines() if line]

    joined = _join_non_empty(lines)
    assert "event: ready" in joined
    assert "event: end" in joined
    assert "event: run.complete" not in joined
    assert '"reason":"terminal_status"' in joined
    assert '"status":"cancelled"' in joined


async def test_run_events_stream_endpoint_emits_terminal_end_after_status_transition(
    async_client,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(
        workspace_id=workspace_id,
        name="SSE Transition Config",
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
        status=RunStatus.RUNNING,
    )
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    async def _mark_terminal() -> None:
        await anyio.sleep(0.5)

        def _commit_terminal() -> None:
            persisted = db_session.get(Run, run.id)
            assert persisted is not None
            persisted.status = RunStatus.CANCELLED
            persisted.completed_at = utc_now()
            persisted.error_message = "Run cancelled by user"
            db_session.commit()

        await anyio.to_thread.run_sync(_commit_terminal)

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    with anyio.fail_after(12):
        async with anyio.create_task_group() as tg:
            tg.start_soon(_mark_terminal)
            async with async_client.stream(
                "GET",
                f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/events/stream",
                headers=headers,
            ) as response:
                assert response.status_code == 200
                lines = [line async for line in response.aiter_lines() if line]

    joined = _join_non_empty(lines)
    assert "event: ready" in joined
    assert "event: end" in joined
    assert '"status":"cancelled"' in joined


async def test_events_download_uses_document_stem_and_timestamp_filename(
    async_client,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(workspace_id=workspace_id, name="Download Name Config")
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    document = make_document(workspace_id=workspace_id, filename="Quarterly Intake.xlsx")
    db_session.add(document)
    await anyio.to_thread.run_sync(db_session.flush)

    run = make_run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        file_version_id=document.current_version_id,
        status=RunStatus.SUCCEEDED,
    )
    run.created_at = datetime(2026, 2, 9, 21, 45, 0, tzinfo=UTC)
    run.completed_at = utc_now()
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    events_blob_name = f"{workspace_id}/runs/{run.id}/logs/events.ndjson"
    events_payload = b'{"timestamp":"2026-02-09T21:45:01Z","event":"run.complete","data":{}}\n'
    storage = build_storage_adapter(settings)
    storage.write(events_blob_name, io.BytesIO(events_payload))

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/events/download",
        headers=headers,
    )

    assert response.status_code == 200
    assert (
        'filename="Quarterly Intake_20260209T214500Z.ndjson"'
        in response.headers["content-disposition"]
    )
    assert response.text == events_payload.decode("utf-8")


async def test_events_download_falls_back_to_run_id_filename_when_input_missing(
    async_client,
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(workspace_id=workspace_id, name="Download Fallback Config")
    db_session.add(configuration)
    await anyio.to_thread.run_sync(db_session.flush)

    run = Run(
        workspace_id=workspace_id,
        configuration_id=configuration.id,
        input_file_version_id=None,
        deps_digest="sha256:fallback",
        status=RunStatus.SUCCEEDED,
        created_at=datetime(2026, 2, 9, 21, 45, 0, tzinfo=UTC),
    )
    run.completed_at = utc_now()
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    events_blob_name = f"{workspace_id}/runs/{run.id}/logs/events.ndjson"
    events_payload = b'{"timestamp":"2026-02-09T21:45:01Z","event":"run.complete","data":{}}\n'
    storage = build_storage_adapter(settings)
    storage.write(events_blob_name, io.BytesIO(events_payload))

    headers = await auth_headers(async_client, seed_identity.workspace_owner)
    response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/events/download",
        headers=headers,
    )

    assert response.status_code == 200
    expected = f'filename="run-{str(run.id)[:8]}_20260209T214500Z.ndjson"'
    assert expected in response.headers["content-disposition"]
    assert response.text == events_payload.decode("utf-8")


async def test_run_events_stream_requires_workspace_permission(
    async_client,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(workspace_id=workspace_id, name="SSE RBAC Config")
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
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.orphan)
    response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/runs/{run.id}/events/stream",
        headers=headers,
    )
    assert response.status_code == 403


async def test_run_events_stream_returns_not_found_when_workspace_does_not_match_run(
    async_client,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    configuration = make_configuration(workspace_id=workspace_id, name="SSE Scope Config")
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
    db_session.add(run)
    await anyio.to_thread.run_sync(db_session.commit)

    headers = await auth_headers(async_client, seed_identity.admin)
    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.secondary_workspace_id}/runs/{run.id}/events/stream",
        headers=headers,
    )
    assert response.status_code == 404
