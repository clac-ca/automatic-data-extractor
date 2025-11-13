from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from apps.api.app.features.builds.models import ConfigurationBuild, ConfigurationBuildStatus
from apps.api.app.features.configs.models import Configuration, ConfigurationStatus
from apps.api.app.features.runs.models import RunStatus
from apps.api.app.features.runs.schemas import (
    RunCompletedEvent,
    RunCreateOptions,
    RunLogEvent,
)
from apps.api.app.features.runs.service import RunExecutionContext, RunsService
from apps.api.app.features.workspaces.models import Workspace
from apps.api.app.settings import Settings
from apps.api.app.shared.core.time import utc_now
from apps.api.app.shared.db.mixins import generate_ulid


async def _prepare_service(
    session,
    tmp_path: Path,
    *,
    safe_mode: bool = False,
) -> tuple[RunsService, RunExecutionContext]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_ulid().lower()}")
    session.add(workspace)
    await session.flush()

    configuration = Configuration(
        workspace_id=workspace.id,
        config_id=generate_ulid(),
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
        config_version=1,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()

    venv_root = tmp_path / "venvs"
    venv_dir = venv_root / configuration.config_id
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_name = "python.exe" if os.name == "nt" else "python"
    (bin_dir / python_name).write_text("", encoding="utf-8")

    base_settings = Settings()
    settings = base_settings.model_copy(
        update={
            "venvs_dir": str(venv_root),
            "safe_mode": safe_mode,
        }
    )

    build = ConfigurationBuild(
        workspace_id=workspace.id,
        config_id=configuration.config_id,
        configuration_id=configuration.id,
        build_id=generate_ulid(),
        status=ConfigurationBuildStatus.ACTIVE,
        venv_path=str(venv_dir),
        config_version=configuration.config_version,
        content_digest=configuration.content_digest,
        engine_spec=settings.engine_spec,
        engine_version="0.1.0",
        python_interpreter=settings.python_bin,
        built_at=utc_now(),
    )
    session.add(build)
    await session.commit()

    service = RunsService(session=session, settings=settings)
    run, context = await service.prepare_run(
        config_id=configuration.config_id,
        options=RunCreateOptions(),
    )
    return service, context


@pytest.mark.asyncio()
async def test_stream_run_happy_path_yields_engine_events(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context = await _prepare_service(session, tmp_path)

    async def fake_execute_engine(
        self: RunsService,
        *,
        run,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> AsyncIterator[RunLogEvent | RunCompletedEvent]:
        log = await self._append_log(run.id, "engine output", stream="stdout")
        yield RunLogEvent(
            run_id=run.id,
            created=self._epoch_seconds(log.created_at),
            stream="stdout",
            message="engine output",
        )
        completion = await self._complete_run(
            run,
            status=RunStatus.SUCCEEDED,
            exit_code=0,
        )
        yield RunCompletedEvent(
            run_id=completion.id,
            created=self._epoch_seconds(completion.finished_at),
            status=self._status_literal(completion.status),
            exit_code=completion.exit_code,
            error_message=completion.error_message,
        )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    events = []
    async for event in service.stream_run(context=context, options=RunCreateOptions()):
        events.append(event)

    assert [event.type for event in events] == [
        "run.created",
        "run.started",
        "run.log",
        "run.completed",
    ]

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    logs = await service.get_logs(run_id=context.run_id)
    assert [entry.message for entry in logs.entries] == ["engine output"]
    assert logs.next_after_id is None


@pytest.mark.asyncio()
async def test_stream_run_handles_engine_failure(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context = await _prepare_service(session, tmp_path)

    async def failing_engine(*args, **kwargs):  # type: ignore[no-untyped-def]
        if False:
            yield  # pragma: no cover
        raise RuntimeError("boom")

    monkeypatch.setattr(RunsService, "_execute_engine", failing_engine)

    events = []
    async for event in service.stream_run(context=context, options=RunCreateOptions()):
        events.append(event)

    assert events[-1].type == "run.completed"
    assert events[-1].status == "failed"
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
    service, context = await _prepare_service(session, tmp_path)

    async def cancelling_engine(*args, **kwargs):  # type: ignore[no-untyped-def]
        if False:
            yield  # pragma: no cover
        raise asyncio.CancelledError()

    monkeypatch.setattr(RunsService, "_execute_engine", cancelling_engine)

    events = []
    with pytest.raises(asyncio.CancelledError):
        async for event in service.stream_run(context=context, options=RunCreateOptions()):
            events.append(event)

    assert events[-1].type == "run.completed"
    assert events[-1].status == "canceled"

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.CANCELED
    assert run.error_message == "Run execution cancelled"


@pytest.mark.asyncio()
async def test_stream_run_validate_only_short_circuits(
    session,
    tmp_path: Path,
) -> None:
    service, context = await _prepare_service(session, tmp_path)

    events = []
    async for event in service.stream_run(
        context=context,
        options=RunCreateOptions(validate_only=True),
    ):
        events.append(event)

    assert [event.type for event in events] == [
        "run.created",
        "run.started",
        "run.log",
        "run.completed",
    ]
    assert events[-1].status == "succeeded"

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    assert run.summary == "Validation-only execution"
    logs = await service.get_logs(run_id=context.run_id)
    assert logs.entries[0].message == "Run options: validate-only mode"


@pytest.mark.asyncio()
async def test_stream_run_respects_safe_mode(session, tmp_path: Path) -> None:
    service, context = await _prepare_service(session, tmp_path, safe_mode=True)

    events = []
    async for event in service.stream_run(context=context, options=RunCreateOptions()):
        events.append(event)

    assert [event.type for event in events] == [
        "run.created",
        "run.started",
        "run.log",
        "run.completed",
    ]
    assert events[-1].status == "succeeded"
    assert events[-1].exit_code == 0

    run = await service.get_run(context.run_id)
    assert run is not None
    assert run.summary == "Safe mode skip"
    logs = await service.get_logs(run_id=context.run_id)
    assert logs.entries[-1].message.startswith("ADE safe mode enabled")
