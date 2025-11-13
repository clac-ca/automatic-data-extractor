from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.features.configs.models import Configuration, ConfigurationStatus
from apps.api.app.features.runs.models import Run, RunLog, RunStatus
from apps.api.app.features.workspaces.models import Workspace
from apps.api.app.shared.db.mixins import generate_ulid


async def _create_configuration(session: AsyncSession) -> tuple[Workspace, Configuration]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_ulid().lower()}")
    session.add(workspace)
    await session.flush()

    configuration = Configuration(
        workspace_id=workspace.id,
        config_id=generate_ulid(),
        display_name="Config",  # minimal metadata for FK relations
        status=ConfigurationStatus.ACTIVE,
        config_version=1,
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
        configuration_id=configuration.id,
        workspace_id=workspace.id,
        config_id=configuration.config_id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await session.refresh(run, attribute_names=["logs"])

    assert run.status is RunStatus.QUEUED
    assert isinstance(run.created_at, datetime)
    assert run.started_at is None
    assert run.finished_at is None
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
