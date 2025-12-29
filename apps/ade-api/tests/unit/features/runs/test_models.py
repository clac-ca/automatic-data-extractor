from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.db.mixins import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.models import (
    Build,
    BuildStatus,
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentSource,
    DocumentStatus,
    Run,
    RunStatus,
    Workspace,
)


async def _create_configuration(session: AsyncSession) -> tuple[Workspace, Configuration]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    await session.flush()

    configuration_id = generate_uuid7()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",  # minimal metadata for FK relations
        status=ConfigurationStatus.ACTIVE,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()
    return workspace, configuration


@pytest.mark.asyncio()
async def test_run_defaults(session: AsyncSession) -> None:
    workspace, configuration = await _create_configuration(session)

    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        fingerprint="fingerprint",
        status=BuildStatus.READY,
        created_at=utc_now(),
    )
    session.add(build)
    await session.flush()

    document = Document(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=12,
        sha256="deadbeef",
        stored_uri="documents/input.csv",
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add(document)
    await session.flush()

    run = Run(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        build_id=build.id,
        input_document_id=document.id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    assert run.status is RunStatus.QUEUED
    assert run.input_document_id == document.id
    assert run.input_sheet_names is None
    assert isinstance(run.created_at, datetime)
    assert run.started_at is None
    assert run.completed_at is None
    assert run.cancelled_at is None
