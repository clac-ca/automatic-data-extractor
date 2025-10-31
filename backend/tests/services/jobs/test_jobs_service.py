"""Service-level tests for the jobs feature."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from starlette.datastructures import Headers

from backend.app.features.configs.service import ConfigService
from backend.app.features.documents.service import DocumentsService
from backend.app.features.jobs.exceptions import (
    ActiveConfigNotFoundError,
    JobExecutionError,
)
from backend.app.features.jobs.models import Job
from backend.app.features.jobs.processor import (
    JobProcessorRequest,
    JobProcessorResult,
    ProcessorError,
    set_job_processor,
)
from backend.app.features.jobs.service import JobsService
from backend.app.features.users.models import User
from backend.app.features.workspaces.models import Workspace
from backend.app.shared.core.config import get_settings
from backend.app.shared.db import generate_ulid
from backend.app.shared.db.session import get_sessionmaker


pytestmark = pytest.mark.asyncio


async def _create_active_config(
    session,
    *,
    workspace_id: str,
    actor_id: str,
    settings,
) -> str:
    service = ConfigService(session=session, settings=settings)
    record = await service.create_config(
        workspace_id=workspace_id,
        title="Jobs Config",
        actor_id=actor_id,
    )
    await service.activate_config(
        workspace_id=workspace_id,
        config_id=record.config_id,
        actor_id=actor_id,
    )
    await session.flush()
    return record.config_id


async def _create_workspace_and_actor(session):
    workspace = Workspace(
        name="Test Workspace",
        slug=f"workspace-{uuid4().hex[:8]}",
    )
    session.add(workspace)
    await session.flush()

    actor = SimpleNamespace(
        id=generate_ulid(),
        email=f"user-{uuid4().hex[:8]}@example.test",
    )
    session.add(User(id=actor.id, email=actor.email, display_name="User"))
    await session.flush()

    return workspace, actor


async def _create_document(session, *, workspace_id: str, actor, settings):
    documents_service = DocumentsService(session=session, settings=settings)
    upload = UploadFile(
        filename="input.txt",
        file=BytesIO(b"payload"),
        headers=Headers({"content-type": "text/plain"}),
    )
    return await documents_service.create_document(
        workspace_id=workspace_id,
        upload=upload,
        actor=actor,
    )


async def test_submit_job_records_success() -> None:
    """Successful job execution should persist metrics and logs."""

    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace, actor = await _create_workspace_and_actor(session)
        document = await _create_document(
            session,
            workspace_id=str(workspace.id),
            actor=actor,
            settings=settings,
        )
        await _create_active_config(
            session,
            workspace_id=str(workspace.id),
            actor_id=actor.id,
            settings=settings,
        )

        service = JobsService(session=session, settings=settings)

        record = await service.submit_job(
            workspace_id=str(workspace.id),
            input_document_id=document.document_id,
            actor_id=actor.id,
        )

        assert record.status == "succeeded"
        assert record.config_id
        assert record.run_key
        assert "duration_ms" in record.metrics
        assert len(record.logs) >= 2

        job = await session.get(Job, record.job_id)
        assert job is not None
        assert job.status == "succeeded"
        assert job.config_id == record.config_id
        assert job.run_key == record.run_key


async def test_submit_job_records_failure_and_raises() -> None:
    """Processor errors should mark the job as failed and raise."""

    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace, actor = await _create_workspace_and_actor(session)
        document = await _create_document(
            session,
            workspace_id=str(workspace.id),
            actor=actor,
            settings=settings,
        )
        config_id = await _create_active_config(
            session,
            workspace_id=str(workspace.id),
            actor_id=actor.id,
            settings=settings,
        )

        service = JobsService(session=session, settings=settings)

        def failing_processor(_: JobProcessorRequest) -> JobProcessorResult:
            raise ProcessorError("Simulated failure")

        set_job_processor(failing_processor)
        try:
            with pytest.raises(JobExecutionError):
                await service.submit_job(
                    workspace_id=str(workspace.id),
                    input_document_id=document.document_id,
                    config_id=config_id,
                    actor_id=actor.id,
                )
        finally:
            set_job_processor(None)

        job_result = await session.execute(
            select(Job).where(Job.workspace_id == str(workspace.id))
        )
        job = job_result.scalar_one()
        assert job.status == "failed"
        assert job.metrics.get("error") == "Simulated failure"


async def test_submit_job_without_active_config_raises() -> None:
    """Submitting a job without an active configuration should fail."""

    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace, actor = await _create_workspace_and_actor(session)
        document = await _create_document(
            session,
            workspace_id=str(workspace.id),
            actor=actor,
            settings=settings,
        )

        service = JobsService(session=session, settings=settings)

        with pytest.raises(ActiveConfigNotFoundError):
            await service.submit_job(
                workspace_id=str(workspace.id),
                input_document_id=document.document_id,
                actor_id=actor.id,
            )

