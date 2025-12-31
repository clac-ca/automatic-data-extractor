from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from ade_api.features.builds.service import BuildDecision
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.runs.service import (
    RunExecutionContext,
    RunExecutionResult,
    RunPathsSnapshot,
    RunsService,
)
from ade_api.features.system_settings.service import SafeModeService
from ade_api.models import BuildStatus, RunStatus

from tests.unit.features.runs.helpers import build_runs_service


@pytest.mark.asyncio()
async def test_stream_run_requeues_if_build_not_ready(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, fake_builds, _ = await build_runs_service(
        session,
        tmp_path,
        build_status=BuildStatus.QUEUED,
        build_decision=BuildDecision.START_NEW,
    )

    options = RunCreateOptions(input_document_id=str(document.id), force_rebuild=True)
    run = await service.prepare_run(configuration_id=configuration.id, options=options)

    claimed = await service.claim_next_run(worker_id="worker-1")
    assert claimed is not None

    events = [
        event
        async for event in service.stream_run(
            run_id=run.id,
            options=options,
            worker_id="worker-1",
        )
    ]
    assert events and events[0]["event"] == "run.queued"

    refreshed = await service.get_run(run.id)
    assert refreshed is not None
    assert refreshed.status is RunStatus.QUEUED
    assert refreshed.attempt_count == 0
    assert fake_builds.force_calls == [True]


@pytest.mark.asyncio()
async def test_stream_run_respects_persisted_safe_mode_override(
    session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, configuration, document, _fake_builds, settings = await build_runs_service(
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
        yield RunExecutionResult(
            status=RunStatus.SUCCEEDED,
            return_code=0,
            paths_snapshot=RunPathsSnapshot(),
            error_message=None,
        )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    options = RunCreateOptions(input_document_id=str(document.id))
    run = await service.prepare_run(configuration_id=configuration.id, options=options)

    claimed = await service.claim_next_run(worker_id="worker-2")
    assert claimed is not None

    events = [
        event
        async for event in service.stream_run(
            run_id=run.id,
            options=options,
            worker_id="worker-2",
        )
    ]

    assert observed_flags == [False]
    assert events[-1]["event"] == "run.complete"
    completed = await service.get_run(run.id)
    assert completed is not None
    assert completed.status is RunStatus.SUCCEEDED


@pytest.mark.asyncio()
async def test_validate_only_short_circuits_and_completes(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, _fake_builds, _ = await build_runs_service(
        session,
        tmp_path,
        build_status=BuildStatus.READY,
    )
    options = RunCreateOptions(input_document_id=str(document.id), validate_only=True)
    run = await service.prepare_run(configuration_id=configuration.id, options=options)

    claimed = await service.claim_next_run(worker_id="worker-3")
    assert claimed is not None

    events = [
        event
        async for event in service.stream_run(
            run_id=run.id,
            options=options,
            worker_id="worker-3",
        )
    ]
    event_types = [event["event"] for event in events]

    assert event_types[0] == "run.queued"
    assert event_types[-1] == "run.complete"
    completed_payload = events[-1].get("data", {})
    assert completed_payload is not None
    failure = completed_payload.get("failure")
    assert failure and failure.get("message") == "Validation-only execution"

    refreshed = await service.get_run(run.id)
    assert refreshed is not None
    assert refreshed.status is RunStatus.SUCCEEDED
