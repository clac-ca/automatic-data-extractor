from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from typing import AsyncIterator

import pytest
from ade_api.schemas.event_record import EventRecord, new_event_record

from ade_api.common.time import utc_now
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
from ade_api.features.builds.service import BuildDecision, BuildExecutionContext
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.service import (
    RunExecutionContext,
    RunExecutionResult,
    RunPathsSnapshot,
    RunsService,
)
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.system_settings.service import SafeModeService
from ade_api.infra.db.mixins import generate_uuid7
from ade_api.infra.storage import workspace_config_root, workspace_documents_root
from ade_api.settings import Settings


class FakeBuildsService:
    """Minimal build service stub used to avoid real env creation."""

    def __init__(
        self,
        *,
        build: Build,
        context: BuildExecutionContext | None,
        events: list[EventRecord] | None,
        venv_path: Path,
    ) -> None:
        self.build = build
        self.context = context
        self.events = events or []
        self.venv_path = venv_path
        self.force_calls: list[bool] = []

    async def ensure_build_for_run(
        self,
        *,
        workspace_id: str,
        configuration_id: str,
        force_rebuild: bool,
        run_id,
        reason: str = "on_demand",
    ) -> tuple[Build, BuildExecutionContext | None]:
        self.force_calls.append(bool(force_rebuild))
        return self.build, self.context

    async def stream_build(self, *, context, options) -> AsyncIterator[EventRecord]:
        for event in self.events:
            yield event
        self.build.status = BuildStatus.READY
        self.build.exit_code = 0

    async def get_build_or_raise(self, build_id: str, workspace_id: str | None = None) -> Build:
        return self.build

    async def ensure_local_env(self, *, build: Build) -> Path:
        self.venv_path.parent.mkdir(parents=True, exist_ok=True)
        self.venv_path.mkdir(parents=True, exist_ok=True)
        return self.venv_path

    def event_log_reader(self, *_, **__):
        class _Reader:
            def iter(self, after_sequence: int = 0):
                return []

        return _Reader()

    @asynccontextmanager
    async def subscribe_to_events(self, *_args, **_kwargs):
        yield iter(())


async def _build_service(
    session,
    tmp_path: Path,
    *,
    safe_mode: bool = False,
    build_status: BuildStatus = BuildStatus.READY,
    build_decision: BuildDecision = BuildDecision.START_NEW,
    build_events: list[EventRecord] | None = None,
) -> tuple[RunsService, Configuration, Document, FakeBuildsService, Settings]:
    data_root = tmp_path / "data"
    settings = Settings(
        workspaces_dir=data_root / "workspaces",
        documents_dir=data_root / "workspaces",
        runs_dir=data_root / "workspaces",
        venvs_dir=data_root / "venvs",
        pip_cache_dir=data_root / "cache" / "pip",
        safe_mode=safe_mode,
    )

    workspace = Workspace(name="Test Workspace", slug=f"ws-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    await session.flush()

    configuration = Configuration(
        workspace_id=workspace.id,
        display_name="Demo Config",
        status=ConfigurationStatus.ACTIVE,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=build_status,
        created_at=utc_now(),
    )
    session.add(build)
    configuration.active_build_id = build.id
    await session.flush()

    config_root = workspace_config_root(settings, workspace.id, configuration.id)
    config_root.mkdir(parents=True, exist_ok=True)
    venv_root = Path(settings.venvs_dir) / "demo-venv"
    build_ctx = BuildExecutionContext(
        build_id=build.id,
        configuration_id=configuration.id,
        workspace_id=workspace.id,
        config_path=str(config_root),
        venv_root=str(venv_root),
        python_bin=None,
        engine_spec="engine-spec",
        engine_version_hint=None,
        pip_cache_dir=None,
        timeout_seconds=30.0,
        decision=build_decision,
        fingerprint="fp",
        run_id=None,
        reuse_summary=None,
        reason=None,
    )
    if build_status is BuildStatus.READY:
        build_ctx = None

    doc_storage = DocumentStorage(workspace_documents_root(settings, workspace.id))
    document_id = generate_uuid7()
    stored_uri = doc_storage.make_stored_uri(str(document_id))
    document_path = doc_storage.path_for(stored_uri)
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_text("name\nAlice\n", encoding="utf-8")

    document = Document(
        id=document_id,
        workspace_id=workspace.id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=document_path.stat().st_size,
        sha256="deadbeef",
        stored_uri=stored_uri,
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add(document)
    await session.commit()

    safe_mode_service = SafeModeService(session=session, settings=settings)
    service = RunsService(
        session=session,
        settings=settings,
        safe_mode_service=safe_mode_service,
    )
    fake_builds = FakeBuildsService(
        build=build,
        context=build_ctx,
        events=build_events,
        venv_path=venv_root / ".venv",
    )
    service._builds_service = fake_builds  # type: ignore[attr-defined]

    return service, configuration, document, fake_builds, settings


@pytest.mark.asyncio()
async def test_prepare_run_emits_queued_event(session, tmp_path: Path) -> None:
    service, configuration, document, fake_builds, _ = await _build_service(
        session,
        tmp_path,
        build_status=BuildStatus.READY,
    )

    options = RunCreateOptions(input_document_id=str(document.id))
    run, context = await service.prepare_run(configuration_id=configuration.id, options=options)

    assert run.status is RunStatus.QUEUED
    assert Path(context.venv_path).name == ".venv"
    assert fake_builds.force_calls == [False]
    assert run.input_document_id == document.id
    assert run.input_sheet_names is None

    events, _ = await service.get_run_events(run_id=run.id, limit=5)
    assert events and events[0]["event"] == "run.queued"
    queued_options = events[0].get("data", {}).get("options") or {}
    assert queued_options.get("input_document_id") == str(document.id)


@pytest.mark.asyncio()
async def test_execute_engine_sets_config_package_flag(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, configuration, document, _fake_builds, settings = await _build_service(
        session,
        tmp_path,
        build_status=BuildStatus.READY,
    )
    options = RunCreateOptions(input_document_id=str(document.id))
    run, context = await service.prepare_run(configuration_id=configuration.id, options=options)

    captured_command: list[str] | None = None

    class FakeRunner:
        def __init__(self, *, command, env) -> None:  # noqa: ARG002
            nonlocal captured_command
            captured_command = command
            self.returncode = 0

        async def stream(self):
            if False:  # pragma: no cover
                yield None

    monkeypatch.setattr("ade_api.features.runs.service.EngineSubprocessRunner", FakeRunner)

    frames = [
        frame
        async for frame in service._execute_engine(
            run=run,
            context=context,
            options=options,
            safe_mode_enabled=False,
        )
    ]

    assert captured_command is not None
    assert "--config-package" in captured_command
    idx = captured_command.index("--config-package")
    expected = workspace_config_root(settings, configuration.workspace_id, configuration.id)
    assert captured_command[idx + 1] == str(expected)
    assert any(isinstance(frame, RunExecutionResult) for frame in frames)


@pytest.mark.asyncio()
async def test_stream_run_waits_for_build_and_forwards_events(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_event = new_event_record(
        event="build.start",
        data={"status": "building"},
    )
    service, configuration, document, fake_builds, _ = await _build_service(
        session,
        tmp_path,
        build_status=BuildStatus.QUEUED,
        build_decision=BuildDecision.START_NEW,
        build_events=[build_event],
    )

    async def fake_execute_engine(
        self: RunsService,
        *,
        run,
        context: RunExecutionContext,
        options: RunCreateOptions,
        safe_mode_enabled: bool = False,
    ) -> AsyncIterator[RunExecutionResult]:
        summary = await self._build_placeholder_summary(
            run=run,
            status=RunStatus.SUCCEEDED,
            message="engine finished",
        )
        summary_json = self._serialize_summary(summary)
        yield RunExecutionResult(
            status=RunStatus.SUCCEEDED,
            return_code=0,
            summary_model=summary,
            summary_json=summary_json,
            paths_snapshot=RunPathsSnapshot(),
            error_message=None,
        )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    options = RunCreateOptions(input_document_id=str(document.id), force_rebuild=True)
    run, context = await service.prepare_run(configuration_id=configuration.id, options=options)

    assert run.status is RunStatus.WAITING_FOR_BUILD

    events = [event async for event in service.stream_run(context=context, options=options)]
    event_types = [event["event"] for event in events]

    assert "build.start" in event_types
    assert any(
        evt.get("event") == "console.line"
        and (evt.get("data", {}).get("message") or "").startswith("Configuration build completed")
        for evt in events
    )
    assert event_types[-1] == "run.complete"

    refreshed = await service.get_run(run.id)
    assert refreshed is not None
    assert refreshed.status is RunStatus.SUCCEEDED
    assert fake_builds.force_calls == [True]


@pytest.mark.asyncio()
async def test_stream_run_respects_persisted_safe_mode_override(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, configuration, document, fake_builds, settings = await _build_service(
        session,
        tmp_path,
        safe_mode=True,
        build_status=BuildStatus.READY,
    )
    safe_mode_service = SafeModeService(session=session, settings=settings)
    await safe_mode_service.update_status(
        enabled=False, detail="Persisted override disables safe mode"
    )
    service._safe_mode_service = safe_mode_service  # type: ignore[attr-defined]

    observed_flags: list[bool] = []

    async def fake_execute_engine(
        self: RunsService,
        *,
        run,
        context: RunExecutionContext,
        options: RunCreateOptions,
        safe_mode_enabled: bool = False,
    ) -> AsyncIterator[RunExecutionResult]:
        observed_flags.append(safe_mode_enabled)
        summary = await self._build_placeholder_summary(
            run=run,
            status=RunStatus.SUCCEEDED,
            message="engine ran",
        )
        summary_json = self._serialize_summary(summary)
        yield RunExecutionResult(
            status=RunStatus.SUCCEEDED,
            return_code=0,
            summary_model=summary,
            summary_json=summary_json,
            paths_snapshot=RunPathsSnapshot(),
            error_message=None,
        )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    options = RunCreateOptions(input_document_id=str(document.id))
    run, context = await service.prepare_run(configuration_id=configuration.id, options=options)

    events = [event async for event in service.stream_run(context=context, options=options)]

    assert observed_flags == [False]
    assert events[-1]["event"] == "run.complete"
    completed = await service.get_run(run.id)
    assert completed is not None
    assert completed.status is RunStatus.SUCCEEDED


@pytest.mark.asyncio()
async def test_validate_only_short_circuits_and_persists_summary(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, fake_builds, _ = await _build_service(
        session,
        tmp_path,
        build_status=BuildStatus.READY,
    )
    options = RunCreateOptions(input_document_id=str(document.id), validate_only=True)
    run, context = await service.prepare_run(configuration_id=configuration.id, options=options)

    events = [event async for event in service.stream_run(context=context, options=options)]
    event_types = [event["event"] for event in events]

    assert event_types[0] == "run.queued"
    assert event_types[-1] == "run.complete"
    completed_payload = events[-1].get("data", {})
    assert completed_payload is not None
    assert completed_payload.get("summary") is None
    failure = completed_payload.get("failure")
    assert failure and failure.get("message") == "Validation-only execution"

    refreshed = await service.get_run(run.id)
    assert refreshed is not None
    assert refreshed.status is RunStatus.SUCCEEDED
    assert refreshed.summary is not None
