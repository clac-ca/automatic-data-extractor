from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ade_engine.schemas import AdeEvent

from ade_api.features.builds.models import BuildStatus
from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.features.configs.storage import compute_config_digest
from ade_api.features.documents.models import Document, DocumentSource, DocumentStatus
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.models import RunStatus
from ade_api.features.runs.schemas import RunCompletedEvent, RunCreateOptions, RunLogEvent
from ade_api.features.runs.service import RunExecutionContext, RunsService
from ade_api.features.system_settings.service import SafeModeService
from ade_api.features.workspaces.models import Workspace
from ade_api.settings import Settings
from ade_api.shared.core.time import utc_now
from ade_api.shared.db.mixins import generate_ulid
from ade_api.storage_layout import config_venv_path, workspace_config_root, workspace_documents_root


async def _prepare_service(
    session,
    tmp_path: Path,
    *,
    safe_mode: bool = False,
) -> tuple[RunsService, RunExecutionContext, Document]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_ulid().lower()}")
    session.add(workspace)
    await session.flush()

    configuration_id = generate_ulid()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
        configuration_version=1,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()

    workspaces_dir = tmp_path / "workspaces"
    documents_dir = workspaces_dir
    runs_dir = workspaces_dir

    base_settings = Settings()
    settings = base_settings.model_copy(
        update={
            "workspaces_dir": workspaces_dir,
            "safe_mode": safe_mode,
            "documents_dir": documents_dir,
            "runs_dir": runs_dir,
        }
    )

    venv_dir = config_venv_path(settings, workspace.id, configuration.id)
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_name = "python.exe" if os.name == "nt" else "python"
    (bin_dir / python_name).write_text("", encoding="utf-8")
    config_root = workspace_config_root(settings, workspace.id, configuration.id)
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.0.1'\n",
        encoding="utf-8",
    )
    digest = compute_config_digest(config_root)

    document_id = generate_ulid()
    storage = DocumentStorage(workspace_documents_root(settings, workspace.id))
    stored_uri = storage.make_stored_uri(document_id)
    source_path = storage.path_for(stored_uri)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("name\nAlice", encoding="utf-8")

    document = Document(
        id=document_id,
        workspace_id=workspace.id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=source_path.stat().st_size,
        sha256="deadbeef",
        stored_uri=stored_uri,
        status=DocumentStatus.UPLOADED.value,
        source=DocumentSource.MANUAL_UPLOAD.value,
        expires_at=utc_now(),
    )
    session.add(document)

    configuration.build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
    configuration.engine_spec = settings.engine_spec  # type: ignore[attr-defined]
    configuration.engine_version = "0.2.0"  # type: ignore[attr-defined]
    configuration.python_interpreter = settings.python_bin  # type: ignore[attr-defined]
    configuration.python_version = "3.12.1"  # type: ignore[attr-defined]
    configuration.last_build_finished_at = utc_now()  # type: ignore[attr-defined]
    configuration.built_content_digest = digest  # type: ignore[attr-defined]
    configuration.content_digest = digest
    await session.commit()

    safe_mode_service = SafeModeService(session=session, settings=settings)
    service = RunsService(
        session=session,
        settings=settings,
        safe_mode_service=safe_mode_service,
    )
    run, context = await service.prepare_run(
        configuration_id=configuration.id,
        options=RunCreateOptions(input_document_id=document.id),
    )
    return service, context, document


@pytest.mark.asyncio()
async def test_stream_run_happy_path_yields_engine_events(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    run_options = RunCreateOptions(input_document_id=document.id)

    async def fake_execute_engine(
        self: RunsService,
        *,
        run,
        context: RunExecutionContext,
        options: RunCreateOptions,
        ) -> AsyncIterator[AdeEvent]:
            log = await self._append_log(run.id, "engine output", stream="stdout")
            yield self._ade_event(
                run=run,
                type_="run.log.delta",
                log_payload={
                    "stream": "stdout",
                    "message": "engine output",
                    "created": self._epoch_seconds(log.created_at),
                },
            )
            telemetry = self._ade_event(
                run=run,
                type_="run.pipeline.progress",
                run_payload={"phase": "extracting"},
            )
            await self._append_log(run.id, telemetry.model_dump_json(), stream="stdout")
            yield telemetry
            completion = await self._complete_run(
                run,
                status=RunStatus.SUCCEEDED,
                exit_code=0,
            )
            yield self._ade_event(
                run=completion,
                type_="run.completed",
                run_payload={
                    "status": self._status_literal(completion.status),
                    "execution_summary": {"exit_code": completion.exit_code},
                },
            )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    events = []
    async for event in service.stream_run(context=context, options=run_options):
        events.append(event)

    assert events[0].type == "run.created"
    assert events[1].type == "run.started"
    assert events[2].type == "run.log.delta"
    assert events[3].type == "run.pipeline.progress"
    assert events[4].type == "run.completed"

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    logs = await service.get_logs(run_id=context.run_id)
    messages = [entry.message for entry in logs.entries]
    assert messages[0] == "engine output"
    telemetry = AdeEvent.model_validate_json(messages[1])
    assert telemetry.type == "run.pipeline.progress"
    assert logs.next_after_id is None


@pytest.mark.asyncio()
async def test_stream_run_handles_engine_failure(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    run_options = RunCreateOptions(input_document_id=document.id)

    async def failing_engine(*args, **kwargs):  # type: ignore[no-untyped-def]
        if False:
            yield  # pragma: no cover
        raise RuntimeError("boom")

    monkeypatch.setattr(RunsService, "_execute_engine", failing_engine)

    events = []
    async for event in service.stream_run(context=context, options=run_options):
        events.append(event)

    assert events[-1].type == "run.completed"
    assert events[-1].run is not None
    assert events[-1].run["status"] == "failed"
    failure_logs = await service.get_logs(run_id=context.run_id)
    assert failure_logs.entries[-1].message.startswith("ADE run failed: boom")

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.FAILED
    assert run.error_message == "boom"


@pytest.mark.asyncio()
async def test_stream_run_handles_cancelled_execution(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    run_options = RunCreateOptions(input_document_id=document.id)

    async def cancelling_engine(*args, **kwargs):  # type: ignore[no-untyped-def]
        if False:
            yield  # pragma: no cover
        raise asyncio.CancelledError()

    monkeypatch.setattr(RunsService, "_execute_engine", cancelling_engine)

    events = []
    with pytest.raises(asyncio.CancelledError):
        async for event in service.stream_run(context=context, options=run_options):
            events.append(event)

    assert events[-1].type == "run.completed"
    assert events[-1].run is not None
    assert events[-1].run["status"] == "canceled"

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.CANCELED


@pytest.mark.asyncio()
async def test_force_rebuild_triggers_rebuild(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)

    rebuild_called = False

    async def fake_rebuild(self, *, configuration, config_root, venv_path, digest):  # type: ignore[no-untyped-def]
        nonlocal rebuild_called
        rebuild_called = True
        configuration.build_status = BuildStatus.ACTIVE  # type: ignore[assignment]
        configuration.built_content_digest = digest  # type: ignore[attr-defined]
        configuration.last_build_finished_at = utc_now()  # type: ignore[attr-defined]

    monkeypatch.setattr(RunsService, "_rebuild_configuration_env", fake_rebuild)

    options = RunCreateOptions(input_document_id=document.id, force_rebuild=True)
    run, _ = await service.prepare_run(configuration_id=context.configuration_id, options=options)

    assert rebuild_called is True
    assert run.build_id is not None


@pytest.mark.asyncio()
async def test_stream_run_validate_only_short_circuits(
    session,
    tmp_path: Path,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    run_options = RunCreateOptions(input_document_id=document.id, validate_only=True)

    events = []
    async for event in service.stream_run(
        context=context,
        options=run_options,
    ):
        events.append(event)

    assert [event.type for event in events] == [
        "run.created",
        "run.started",
        "run.log.delta",
        "run.completed",
    ]
    assert events[-1].run is not None
    assert events[-1].run["status"] == "succeeded"
    assert events[-1].run is not None
    assert events[-1].run["summary"]["run"]["failure_message"] == "Validation-only execution"

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    summary = json.loads(run.summary or "{}")
    assert summary.get("run", {}).get("status") == "succeeded"
    assert summary.get("run", {}).get("failure_message") == "Validation-only execution"
    logs = await service.get_logs(run_id=context.run_id)
    assert logs.entries[0].message == "Run options: validate-only mode"


@pytest.mark.asyncio()
async def test_stream_run_respects_safe_mode(session, tmp_path: Path) -> None:
    service, context, document = await _prepare_service(session, tmp_path, safe_mode=True)
    run_options = RunCreateOptions(input_document_id=document.id)

    events = []
    async for event in service.stream_run(context=context, options=run_options):
        events.append(event)

    assert [event.type for event in events] == [
        "run.created",
        "run.started",
        "run.log.delta",
        "run.completed",
    ]
    assert events[-1].run is not None
    assert events[-1].run["status"] == "succeeded"
    assert events[-1].run["execution_summary"]["exit_code"] == 0
    assert events[-1].run is not None
    assert events[-1].run["summary"]["run"]["failure_message"] == "Safe mode skip"

    run = await service.get_run(context.run_id)
    assert run is not None
    summary = json.loads(run.summary or "{}")
    assert summary.get("run", {}).get("status") == "succeeded"
    assert summary.get("run", {}).get("failure_message") == "Safe mode skip"
    logs = await service.get_logs(run_id=context.run_id)
    assert "safe mode" in logs.entries[-1].message.lower()
