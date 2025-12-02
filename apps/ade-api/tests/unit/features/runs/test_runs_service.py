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
from ade_engine.schemas import AdeEvent, ConsoleLinePayload, RunCompletedPayload

from ade_api.features.builds.fingerprint import compute_build_fingerprint
from ade_api.core.models import (
    Build,
    BuildStatus,
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentSource,
    DocumentStatus,
    RunStatus,
    Workspace,
)
from ade_api.features.builds.service import BuildExecutionContext
from ade_api.common.encoding import json_dumps
from ade_api.features.configs.storage import compute_config_digest
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.runs.service import RunExecutionContext, RunsService
from ade_api.features.system_settings.service import SafeModeService
from ade_api.settings import Settings
from ade_api.common.time import utc_now
from ade_api.infra.db.mixins import generate_uuid7
from ade_api.infra.storage import (
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
    workspace = Workspace(name="Acme", slug=f"acme-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    await session.flush()

    configuration_id = generate_uuid7()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
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

    build_id = generate_uuid7()
    venv_dir = build_venv_path(settings, str(workspace.id), str(configuration.id), str(build_id))
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_name = "python.exe" if os.name == "nt" else "python"
    (bin_dir / python_name).write_text("", encoding="utf-8")
    config_root = workspace_config_root(settings, str(workspace.id), str(configuration.id))
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

    document_id = generate_uuid7()
    storage = DocumentStorage(workspace_documents_root(settings, workspace.id))
    stored_uri = storage.make_stored_uri(str(document_id))
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
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add(document)

    marker = build_venv_marker_path(
        settings, str(workspace.id), str(configuration.id), str(build_id)
    )
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json_dumps({"build_id": build_id, "fingerprint": fingerprint}, indent=2),
        encoding="utf-8",
    )

    configuration.active_build_id = build_id  # type: ignore[attr-defined]
    configuration.active_build_fingerprint = fingerprint  # type: ignore[attr-defined]
    configuration.content_digest = digest
    await session.commit()

    safe_mode_service = SafeModeService(session=session, settings=settings)
    service = RunsService(
        session=session,
        settings=settings,
        safe_mode_service=safe_mode_service,
    )

    async def _noop_run_to_completion(*, context, options):  # type: ignore[no-untyped-def]
        return None

    async def _ensure_env_stub(build, **_kwargs):  # type: ignore[no-untyped-def]
        return venv_dir

    service._builds_service.run_to_completion = _noop_run_to_completion  # type: ignore[attr-defined]
    service._builds_service.ensure_local_env = _ensure_env_stub  # type: ignore[attr-defined]

    run, context = await service.prepare_run(
        configuration_id=str(configuration.id),
        options=RunCreateOptions(input_document_id=str(document.id)),
    )
    return service, context, document


@pytest.mark.asyncio()
async def test_stream_run_happy_path_yields_engine_events(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    run_options = RunCreateOptions(input_document_id=str(document.id))

    async def fake_execute_engine(
        self: RunsService,
        *,
        run,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> AsyncIterator[AdeEvent]:
        yield await self._event_dispatcher.emit(
            type="console.line",
            source="engine",
            workspace_id=str(run.workspace_id),
            configuration_id=str(run.configuration_id),
            run_id=str(run.id),
            build_id=str(run.build_id),
            payload=ConsoleLinePayload(
                scope="run",
                stream="stdout",
                level="info",
                message="engine output",
            ),
        )
        telemetry = await self._event_dispatcher.emit(
            type="run.phase.started",
            source="engine",
            workspace_id=str(run.workspace_id),
            configuration_id=str(run.configuration_id),
            run_id=str(run.id),
            build_id=str(run.build_id),
            payload={"phase": "extracting"},
        )
        yield telemetry
        completion = await self._complete_run(
            run,
            status=RunStatus.SUCCEEDED,
            exit_code=0,
        )
        yield await self._event_dispatcher.emit(
            type="run.completed",
            source="api",
            workspace_id=str(completion.workspace_id),
            configuration_id=str(completion.configuration_id),
            run_id=str(completion.id),
            build_id=str(completion.build_id),
            payload=RunCompletedPayload(
                status="succeeded",
                execution={"exit_code": completion.exit_code},
            ),
        )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    events = []
    async for event in service.stream_run(context=context, options=run_options):
        events.append(event)

    assert events[0].type == "run.queued"
    assert any(evt.type == "console.line" for evt in events[1:])
    assert events[-1].type == "run.completed"

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED


@pytest.mark.asyncio()
async def test_stream_run_handles_engine_failure(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    run_options = RunCreateOptions(input_document_id=str(document.id))

    async def failing_engine(*args, **kwargs):  # type: ignore[no-untyped-def]
        if False:
            yield  # pragma: no cover
        raise RuntimeError("boom")

    monkeypatch.setattr(RunsService, "_execute_engine", failing_engine)

    events = []
    async for event in service.stream_run(context=context, options=run_options):
        events.append(event)

    assert events[-1].type == "run.completed"
    assert events[-1].payload_dict().get("status") == "failed"

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
    run_options = RunCreateOptions(input_document_id=str(document.id))

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
    assert events[-1].payload_dict().get("status") == "canceled"

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

    options = RunCreateOptions(input_document_id=str(document.id), force_rebuild=True)
    run, _ = await service.prepare_run(configuration_id=context.configuration_id, options=options)

    assert rebuild_called is True
    assert run.build_id is not None


@pytest.mark.asyncio()
async def test_stream_run_validate_only_short_circuits(
    session,
    tmp_path: Path,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    run_options = RunCreateOptions(input_document_id=str(document.id), validate_only=True)

    events = []
    async for event in service.stream_run(
        context=context,
        options=run_options,
    ):
        events.append(event)

    assert [event.type for event in events] == [
        "run.queued",
        "run.started",
        "console.line",
        "run.completed",
    ]
    payload = events[-1].payload_dict()
    assert payload.get("status") == "succeeded"
    summary = payload.get("summary", {})
    assert summary.get("run", {}).get("failure_message") == "Validation-only execution"

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    summary = json.loads(run.summary or "{}")
    assert summary.get("run", {}).get("status") == "succeeded"
    assert summary.get("run", {}).get("failure_message") == "Validation-only execution"

    # Validate that the persisted event log also captured completion.
    stored_events, _ = await service.get_run_events(run_id=context.run_id, limit=10)
    assert [event.type for event in stored_events][-1] == "run.completed"


@pytest.mark.asyncio()
async def test_stream_run_emits_build_events_when_requested(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    builds_service = service._builds_service
    workspace_id = context.workspace_id
    configuration_id = context.configuration_id

    build_id = str(generate_uuid7())
    build_ctx = BuildExecutionContext(
        build_id=build_id,
        configuration_id=configuration_id,
        workspace_id=workspace_id,
        config_path=str(tmp_path / "config"),
        venv_root=str(tmp_path / "venvroot"),
        python_bin=None,
        engine_spec="engine-spec",
        engine_version_hint="1.0.0",
        pip_cache_dir=None,
        timeout_seconds=60.0,
        should_run=True,
        fingerprint="abc",
    )

    async def fake_prepare_build(*, workspace_id: str, configuration_id: str, options):  # type: ignore[no-untyped-def]
        build = Build(
            id=build_ctx.build_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            status=BuildStatus.QUEUED,
            created_at=utc_now(),
        )
        return build, build_ctx

    outer_workspace_id = workspace_id

    async def fake_stream_build(*, context, options):  # type: ignore[no-untyped-def]
        yield AdeEvent(
            type="console.line",
            created_at=utc_now(),
            workspace_id=context.workspace_id,
            configuration_id=context.configuration_id,
            build_id=context.build_id,
            payload=ConsoleLinePayload(
                scope="build", stream="stdout", level="info", message="building..."
            ),
        )

    async def fake_get_build_or_raise(build_id: str, workspace_id: str | None = None):  # type: ignore[no-untyped-def]
        return Build(
            id=build_id,
            workspace_id=workspace_id or outer_workspace_id,
            configuration_id=configuration_id,
            status=BuildStatus.ACTIVE,
            created_at=utc_now(),
        )

    async def fake_ensure_local_env(*, build):  # type: ignore[no-untyped-def]
        return tmp_path / "venvroot" / ".venv"

    async def fake_execute_engine(
        self: RunsService,
        *,
        run,
        context: RunExecutionContext,
        options: RunCreateOptions,
        safe_mode_enabled: bool = False,
    ) -> AsyncIterator[AdeEvent]:
        completion = await self._complete_run(
            run,
            status=RunStatus.SUCCEEDED,
            exit_code=0,
            summary=None,
        )
        yield await self._event_dispatcher.emit(
            type="run.completed",
            source="api",
            workspace_id=str(completion.workspace_id),
            configuration_id=str(completion.configuration_id),
            run_id=str(completion.id),
            build_id=str(completion.build_id),
            payload=RunCompletedPayload(
                status="succeeded",
                execution={"exit_code": completion.exit_code},
            ),
        )

    monkeypatch.setattr(builds_service, "prepare_build", fake_prepare_build)
    monkeypatch.setattr(builds_service, "stream_build", fake_stream_build)
    monkeypatch.setattr(builds_service, "get_build_or_raise", fake_get_build_or_raise)
    monkeypatch.setattr(builds_service, "ensure_local_env", fake_ensure_local_env)
    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    run_options = RunCreateOptions(input_document_id=str(document.id))
    _, stream_context = await service.prepare_run(
        configuration_id=configuration_id,
        options=run_options,
    )

    events = []
    async for event in service.stream_run(context=stream_context, options=run_options):
        events.append(event)

    types = [e.type for e in events]
    assert types[0] == "run.queued"
    assert types.count("console.line") >= 1
    assert types[-1] == "run.completed"
    run = await service.get_run(stream_context.run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED


@pytest.mark.asyncio()
async def test_stream_run_respects_safe_mode(session, tmp_path: Path) -> None:
    service, context, document = await _prepare_service(session, tmp_path, safe_mode=True)
    run_options = RunCreateOptions(input_document_id=str(document.id))

    events = []
    async for event in service.stream_run(context=context, options=run_options):
        events.append(event)

    types = [event.type for event in events]
    assert types[0] == "run.queued"
    assert "run.started" in types
    assert "run.completed" in types
    assert any(evt.type == "console.line" for evt in events)
    payload = events[-1].payload_dict()
    assert payload.get("status") == "succeeded"
    assert (payload.get("execution") or {}).get("exit_code") == 0
    artifacts = payload.get("artifacts", {})
    assert "output_paths" in artifacts
    summary = payload.get("summary", {})
    assert summary.get("run", {}).get("failure_message") == "Safe mode skip"

    run = await service.get_run(context.run_id)
    assert run is not None
    summary = json.loads(run.summary or "{}")
    assert summary.get("run", {}).get("status") == "succeeded"
    assert summary.get("run", {}).get("failure_message") == "Safe mode skip"
