"""Job service tests."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import func, select
from starlette.datastructures import Headers

from app import get_settings
from app.db.session import get_sessionmaker
from app.features.configurations.models import Configuration
from app.features.documents.service import DocumentsService
from app.features.jobs.exceptions import JobExecutionError
from app.features.jobs.models import Job
from app.features.jobs.processor import (
    JobProcessorRequest,
    JobProcessorResult,
    get_job_processor,
    set_job_processor,
)
from app.features.jobs.service import JobsService
from app.features.workspaces.models import Workspace


pytestmark = pytest.mark.asyncio


async def test_submit_job_records_metrics() -> None:
    """Successful job execution should persist status, metrics, and logs."""

    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace = Workspace(
            name="Test Workspace",
            slug=f"workspace-{uuid4().hex[:8]}",
        )
        session.add(workspace)
        await session.flush()

        actor = SimpleNamespace(id="user-1", email="user@example.test")

        documents_service = DocumentsService(session=session, settings=settings)
        upload = UploadFile(
            filename="input.txt",
            file=BytesIO(b"payload"),
            headers=Headers({"content-type": "text/plain"}),
        )
        document_record = await documents_service.create_document(
            workspace_id=str(workspace.id),
            upload=upload,
        )

        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.workspace_id == workspace.id,
                Configuration.document_type == "invoice",
            )
        )
        next_version = (result.scalar_one_or_none() or 0) + 1
        configuration = Configuration(
            workspace_id=workspace.id,
            document_type="invoice",
            title="Inline configuration",
            version=next_version,
            is_active=False,
            activated_at=None,
            payload={"tables": [{"columns": ["value"], "rows": [{"value": 1}]}]},
        )
        session.add(configuration)
        await session.flush()

        jobs_service = JobsService(session=session, settings=settings)

        record = await jobs_service.submit_job(
            workspace_id=str(workspace.id),
            input_document_id=document_record.document_id,
            configuration_id=str(configuration.id),
            actor=actor,
        )

        assert record.status == "succeeded"
        assert record.metrics["tables_produced"] == 1

        job = await session.get(Job, record.job_id)
        assert job is not None
        assert job.status == "succeeded"
        assert job.metrics.get("tables_produced") == 1
        assert any(entry.get("message") for entry in job.logs)


async def test_submit_job_records_failure_and_raises() -> None:
    """Processor errors should set failed status and raise JobExecutionError."""

    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace = Workspace(
            name="Test Workspace",
            slug=f"workspace-{uuid4().hex[:8]}",
        )
        session.add(workspace)
        await session.flush()

        actor = SimpleNamespace(id="user-2", email="user2@example.test")

        documents_service = DocumentsService(session=session, settings=settings)
        upload = UploadFile(
            filename="input.txt",
            file=BytesIO(b"payload"),
            headers=Headers({"content-type": "text/plain"}),
        )
        document_record = await documents_service.create_document(
            workspace_id=str(workspace.id),
            upload=upload,
        )

        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.workspace_id == workspace.id,
                Configuration.document_type == "invoice",
            )
        )
        next_version = (result.scalar_one_or_none() or 0) + 1
        configuration = Configuration(
            workspace_id=workspace.id,
            document_type="invoice",
            title="Failing configuration",
            version=next_version,
            is_active=False,
            activated_at=None,
            payload={"simulate_failure": True, "failure_message": "Boom"},
        )
        session.add(configuration)
        await session.flush()

        jobs_service = JobsService(session=session, settings=settings)

        with pytest.raises(JobExecutionError) as excinfo:
            await jobs_service.submit_job(
                workspace_id=str(workspace.id),
                input_document_id=document_record.document_id,
                configuration_id=str(configuration.id),
                actor=actor,
            )

        job_id = excinfo.value.job_id

        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.metrics.get("error") == "Boom"
        assert any("Boom" in entry.get("message", "") for entry in job.logs)


async def test_custom_processor_override_returns_typed_payload() -> None:
    """Overriding the processor hook should drive job execution with typed results."""

    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace = Workspace(
            name="Test Workspace",
            slug=f"workspace-{uuid4().hex[:8]}",
        )
        session.add(workspace)
        await session.flush()

        actor = SimpleNamespace(id="user-3", email="user3@example.test")

        documents_service = DocumentsService(session=session, settings=settings)
        upload = UploadFile(
            filename="input.txt",
            file=BytesIO(b"payload"),
            headers=Headers({"content-type": "text/plain"}),
        )
        document_record = await documents_service.create_document(
            workspace_id=str(workspace.id),
            upload=upload,
        )

        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.workspace_id == workspace.id,
                Configuration.document_type == "invoice",
            )
        )
        next_version = (result.scalar_one_or_none() or 0) + 1
        configuration = Configuration(
            workspace_id=workspace.id,
            document_type="invoice",
            title="Custom processor configuration",
            version=next_version,
            is_active=False,
            activated_at=None,
            payload={},
        )
        session.add(configuration)
        await session.flush()

        jobs_service = JobsService(session=session, settings=settings)

        previous_processor = get_job_processor()

        def _custom_processor(request: JobProcessorRequest) -> JobProcessorResult:
            return JobProcessorResult(
                status="succeeded",
                tables=[{"name": "stub", "rows": []}],
                metrics={"custom": True},
                logs=[{"ts": "2024-01-01T00:00:00Z", "level": "info", "message": "ok"}],
            )

        set_job_processor(_custom_processor)
        try:
            record = await jobs_service.submit_job(
                workspace_id=str(workspace.id),
                input_document_id=document_record.document_id,
                configuration_id=str(configuration.id),
                actor=actor,
            )
        finally:
            set_job_processor(previous_processor)

        assert record.metrics["custom"] is True
        assert record.status == "succeeded"
