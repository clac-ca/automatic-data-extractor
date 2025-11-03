"""Tests covering ADE safe mode protections for job execution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from backend.app.features.jobs.exceptions import JobSubmissionError
from backend.app.features.jobs.orchestrator import JobOrchestrator
from backend.app.features.jobs.schemas import JobSubmitRequest
from backend.app.features.jobs.service import (
    SAFE_MODE_DISABLED_MESSAGE,
    JobsService,
)
from backend.app.features.jobs.storage import JobsStorage
from backend.app.features.configs.spec import ManifestV1
from backend.app.shared.db.session import get_sessionmaker

pytestmark = pytest.mark.asyncio


async def test_submit_job_rejects_when_safe_mode_enabled(
    override_app_settings,
) -> None:
    settings = override_app_settings(safe_mode=True)
    session_factory = get_sessionmaker(settings=settings)

    async with session_factory() as session:
        service = JobsService(session=session, settings=settings)
        payload = JobSubmitRequest(config_version_id="cfg-123")

        with pytest.raises(JobSubmissionError) as excinfo:
            await service.submit_job(
                workspace_id="ws-123",
                request=payload,
                actor=None,
            )

        assert str(excinfo.value) == SAFE_MODE_DISABLED_MESSAGE


async def test_orchestrator_blocks_execution_in_safe_mode(
    override_app_settings,
    tmp_path,
) -> None:
    settings = override_app_settings(safe_mode=True)
    storage = JobsStorage(settings)
    orchestrator = JobOrchestrator(
        storage,
        settings=settings,
        safe_mode_message=SAFE_MODE_DISABLED_MESSAGE,
    )

    config_version = SimpleNamespace(id="cfg-123", package_path=str(tmp_path / "package"))
    manifest = cast(ManifestV1, SimpleNamespace())
    inputs: list[object] = []

    with pytest.raises(RuntimeError) as excinfo:
        await orchestrator.run(
            job_id="job-123",
            config_version=config_version,  # type: ignore[arg-type]
            manifest=manifest,
            trace_id="trace-123",
            input_files=inputs,
            timeout_seconds=5.0,
        )

    assert str(excinfo.value) == SAFE_MODE_DISABLED_MESSAGE
