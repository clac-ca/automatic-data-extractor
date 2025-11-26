from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.features.runs.models import Run, RunLog, RunStatus
from ade_api.features.workspaces.models import Workspace
from ade_api.shared.db.mixins import generate_ulid


async def _create_configuration(session: AsyncSession) -> tuple[Workspace, Configuration]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_ulid().lower()}")
    session.add(workspace)
    await session.flush()

    configuration_id = generate_ulid()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",  # minimal metadata for FK relations
        status=ConfigurationStatus.ACTIVE,
        configuration_version=1,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()
    return workspace, configuration


@pytest.mark.asyncio()
async def test_run_defaults_and_log_cascade(session: AsyncSession) -> None:
    workspace, configuration = await _create_configuration(session)

    run = Run(
        id="run_test",
        workspace_id=workspace.id,
        configuration_id=configuration.id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await session.refresh(run, attribute_names=["logs"])

    assert run.status is RunStatus.QUEUED
    assert run.attempt == 1
    assert run.retry_of_run_id is None
    assert run.trace_id is None
    assert run.configuration_version_id is None
    assert run.input_documents is None
    assert isinstance(run.created_at, datetime)
    assert run.started_at is None
    assert run.finished_at is None
    assert run.canceled_at is None
    assert run.artifact_uri is None
    assert run.output_uri is None
    assert run.logs_uri is None
    assert run.logs == []

    log = RunLog(run_id=run.id, message="hello world")
    session.add(log)
    await session.commit()
    await session.refresh(run, attribute_names=["logs"])

    assert len(run.logs) == 1
    stored_log = run.logs[0]
    assert stored_log.stream == "stdout"
    assert stored_log.message == "hello world"

    await session.delete(run)
    await session.commit()

    remaining_logs = await session.execute(select(RunLog).where(RunLog.run_id == run.id))
    assert remaining_logs.scalars().all() == []
