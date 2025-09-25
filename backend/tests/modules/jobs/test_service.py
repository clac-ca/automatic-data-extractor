from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from sqlalchemy import func, select
from starlette.datastructures import Headers

from backend.api import get_settings
from backend.api.core.message_hub import Message, MessageHub
from backend.api.core.service import ServiceContext
from backend.api.db.session import get_sessionmaker
from backend.api.modules.configurations.models import Configuration
from backend.api.modules.documents.service import DocumentsService
from backend.api.modules.jobs.exceptions import JobExecutionError
from backend.api.modules.jobs.models import Job
from backend.api.modules.jobs.service import JobsService
from backend.api.modules.results.models import ExtractedTable


@pytest.mark.asyncio
async def test_submit_job_emits_events_and_persists_tables() -> None:
    """Successful job execution should emit status events and store tables."""

    settings = get_settings()
    hub = MessageHub()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        context = ServiceContext(
            settings=settings,
            session=session,
            message_hub=hub,
            user=SimpleNamespace(id="user-1", email="user@example.com"),
            workspace=SimpleNamespace(workspace_id="workspace-1"),
        )

        documents_service = DocumentsService(context=context)
        upload = UploadFile(
            filename="input.txt",
            file=BytesIO(b"payload"),
            headers=Headers({"content-type": "text/plain"}),
        )
        document_record = await documents_service.create_document(upload=upload)

        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.document_type == "invoice"
            )
        )
        next_version = (result.scalar_one_or_none() or 0) + 1
        configuration = Configuration(
            document_type="invoice",
            title="Inline configuration",
            version=next_version,
            is_active=False,
            activated_at=None,
            payload={"tables": [{"columns": ["value"], "rows": [{"value": 1}]}]},
        )
        session.add(configuration)
        await session.flush()

        jobs_service = JobsService(context=context)

        events: list[Message] = []

        async def capture(message: Message) -> None:
            events.append(message)

        hub.subscribe("*", capture)
        try:
            record = await jobs_service.submit_job(
                input_document_id=document_record.document_id,
                configuration_id=str(configuration.id),
            )
        finally:
            hub.unsubscribe("*", capture)

        assert record.status == "succeeded"
        assert record.metrics["tables_produced"] == 1
        assert any(event.name == "job.submitted" for event in events)
        assert any(event.name == "job.succeeded" for event in events)

        result = await session.execute(
            select(ExtractedTable).where(ExtractedTable.job_id == record.job_id)
        )
        tables = result.scalars().all()
        assert len(tables) == 1
        assert tables[0].document_id == document_record.document_id


@pytest.mark.asyncio
async def test_submit_job_records_failure_and_raises() -> None:
    """Processor errors should set failed status and raise JobExecutionError."""

    settings = get_settings()
    hub = MessageHub()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        context = ServiceContext(
            settings=settings,
            session=session,
            message_hub=hub,
            user=SimpleNamespace(id="user-2", email="user2@example.com"),
            workspace=SimpleNamespace(workspace_id="workspace-2"),
        )

        documents_service = DocumentsService(context=context)
        upload = UploadFile(
            filename="input.txt",
            file=BytesIO(b"payload"),
            headers=Headers({"content-type": "text/plain"}),
        )
        document_record = await documents_service.create_document(upload=upload)

        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.document_type == "invoice"
            )
        )
        next_version = (result.scalar_one_or_none() or 0) + 1
        configuration = Configuration(
            document_type="invoice",
            title="Failing configuration",
            version=next_version,
            is_active=False,
            activated_at=None,
            payload={"simulate_failure": True, "failure_message": "Boom"},
        )
        session.add(configuration)
        await session.flush()

        jobs_service = JobsService(context=context)

        events: list[Message] = []

        async def capture(message: Message) -> None:
            events.append(message)

        hub.subscribe("*", capture)
        with pytest.raises(JobExecutionError) as excinfo:
            await jobs_service.submit_job(
                input_document_id=document_record.document_id,
                configuration_id=str(configuration.id),
            )
        hub.unsubscribe("*", capture)

        job_id = excinfo.value.job_id
        assert any(event.name == "job.failed" for event in events)

        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.metrics.get("error") == "Boom"
        assert any("Boom" in entry.get("message", "") for entry in job.logs)

        result = await session.execute(
            select(ExtractedTable).where(ExtractedTable.job_id == job_id)
        )
        tables = result.scalars().all()
        assert not tables
