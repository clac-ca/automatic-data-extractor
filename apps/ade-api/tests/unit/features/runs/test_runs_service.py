from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
import tomllib

import pytest
from ade_engine.schemas import AdeEvent

from ade_api.features.builds.fingerprint import compute_build_fingerprint
from ade_api.features.builds.models import Build, BuildStatus
from ade_api.features.builds.service import BuildExecutionContext
from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.features.configs.storage import compute_config_digest
from ade_api.features.documents.models import Document, DocumentSource, DocumentStatus
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.models import RunStatus
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.runs.service import RunExecutionContext, RunsService
from ade_api.features.system_settings.service import SafeModeService
from ade_api.features.workspaces.models import Workspace
from ade_api.settings import Settings
from ade_api.shared.core.time import utc_now
from ade_api.shared.db.mixins import generate_ulid
from ade_api.storage_layout import (
    build_venv_marker_path,
    build_venv_path,
    workspace_config_root,
    workspace_documents_root,
)


def _engine_version_hint(spec: str) -> str | None:
    """Mirror the build service's best-effort engine version detection."""

    spec_path = Path(spec)
    if spec_path.exists() and spec_path.is_dir():
        pyproject = spec_path / "pyproject.toml"
        if pyproject.exists():
            try:
                parsed = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                return parsed.get("project", {}).get("version")
            except Exception:
                return None
    if "==" in spec:
        return spec.split("==", 1)[1]
    return None


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
            "venvs_dir": tmp_path / "venvs",
        }
    )

    build_id = generate_ulid()
    venv_dir = build_venv_path(settings, workspace.id, configuration.id, build_id)
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
    engine_version = _engine_version_hint(settings.engine_spec)

    fingerprint = compute_build_fingerprint(
        config_digest=digest,
        engine_spec=settings.engine_spec,
        engine_version=engine_version,
        python_version=".".join(map(str, sys.version_info[:3])),
        python_bin=settings.python_bin,
        extra={},
    )

    build = Build(
        id=build_id,
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.ACTIVE,
        created_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
        exit_code=0,
        fingerprint=fingerprint,
        config_digest=digest,
        engine_spec=settings.engine_spec,
        engine_version=engine_version,
        python_version=".".join(map(str, sys.version_info[:3])),
        python_interpreter=settings.python_bin or sys.executable,
    )
    session.add(build)

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

    marker = build_venv_marker_path(settings, workspace.id, configuration.id, build_id)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"build_id": build_id, "fingerprint": fingerprint}, indent=2),
        encoding="utf-8",
    )

    configuration.active_build_id = build_id  # type: ignore[attr-defined]
    configuration.active_build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
    configuration.active_build_fingerprint = fingerprint  # type: ignore[attr-defined]
    configuration.active_build_started_at = utc_now()  # type: ignore[attr-defined]
    configuration.active_build_finished_at = utc_now()  # type: ignore[attr-defined]
    configuration.build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
    configuration.engine_spec = settings.engine_spec  # type: ignore[attr-defined]
    configuration.engine_version = engine_version or "0.2.0"  # type: ignore[attr-defined]
    configuration.python_interpreter = settings.python_bin  # type: ignore[attr-defined]
    configuration.python_version = "3.12.1"  # type: ignore[attr-defined]
    configuration.last_build_finished_at = utc_now()  # type: ignore[attr-defined]
    configuration.last_build_id = build_id  # type: ignore[attr-defined]
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
                type_="run.console",
                payload={
                    "stream": "stdout",
                    "level": "info",
                    "message": "engine output",
                    "created": self._epoch_seconds(log.created_at),
                },
            )
            telemetry = self._ade_event(
                run=run,
                type_="run.phase.started",
                payload={"phase": "extracting"},
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
                payload={
                    "status": "succeeded",
                    "execution": {"exit_code": completion.exit_code},
                },
            )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    events = []
    async for event in service.stream_run(context=context, options=run_options):
        events.append(event)

    assert events[0].type == "run.queued"
    assert events[1].type == "run.console"
    assert events[2].type == "run.phase.started"
    assert events[3].type == "run.completed"

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    logs = await service.get_logs(run_id=context.run_id)
    messages = [entry.message for entry in logs.entries]
    assert messages[0] == "engine output"
    telemetry = AdeEvent.model_validate_json(messages[1])
    assert telemetry.type == "run.phase.started"
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
    assert events[-1].model_extra.get("status") == "failed"
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
    assert events[-1].model_extra.get("status") == "canceled"

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
    builds_service = service._builds_service
    existing_build = await builds_service.get_build_or_raise(
        context.build_id, workspace_id=context.workspace_id
    )

    rebuild_called = False

    async def fake_prepare_build(
        *,  # type: ignore[no-untyped-def]
        workspace_id: str,
        configuration_id: str,
        options,
    ):
        nonlocal rebuild_called
        rebuild_called = rebuild_called or bool(options.force)
        return existing_build, BuildExecutionContext(
            build_id=existing_build.id,
            configuration_id=existing_build.configuration_id,
            workspace_id=existing_build.workspace_id,
            config_path=str(context.venv_path),
            venv_root=str(Path(context.venv_path).parent),
            python_bin=existing_build.python_interpreter,
            engine_spec=existing_build.engine_spec or "",
            engine_version_hint=existing_build.engine_version,
            pip_cache_dir=None,
            timeout_seconds=300.0,
            should_run=False,
            fingerprint=existing_build.fingerprint or "",
            reuse_summary="reuse-stub",
        )

    async def fake_run_to_completion(*, context, options):  # type: ignore[no-untyped-def]
        return None

    async def fake_ensure_local_env(*, build):  # type: ignore[no-untyped-def]
        return Path(context.venv_path)

    monkeypatch.setattr(builds_service, "prepare_build", fake_prepare_build)
    monkeypatch.setattr(builds_service, "run_to_completion", fake_run_to_completion)
    monkeypatch.setattr(builds_service, "ensure_local_env", fake_ensure_local_env)

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
        "run.queued",
        "run.started",
        "run.console",
        "run.completed",
    ]
    assert events[-1].model_extra.get("status") == "succeeded"
    assert events[-1].model_extra.get("run_summary", {}).get("run", {}).get("failure_message") == "Validation-only execution"

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
        "run.queued",
        "run.started",
        "run.console",
        "run.completed",
    ]
    assert events[-1].model_extra.get("status") == "succeeded"
    assert (events[-1].model_extra.get("execution") or {}).get("exit_code") == 0
    assert events[-1].model_extra.get("run_summary", {}).get("run", {}).get("failure_message") == "Safe mode skip"

    run = await service.get_run(context.run_id)
    assert run is not None
    summary = json.loads(run.summary or "{}")
    assert summary.get("run", {}).get("status") == "succeeded"
    assert summary.get("run", {}).get("failure_message") == "Safe mode skip"
    logs = await service.get_logs(run_id=context.run_id)
    assert "safe mode" in logs.entries[-1].message.lower()
