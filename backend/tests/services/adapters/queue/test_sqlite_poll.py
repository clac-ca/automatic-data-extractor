"""SQLitePollingQueue adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.shared.db.session import get_sessionmaker
from backend.app.shared.adapters.queue.sqlite_poll import SQLitePollingQueue
from backend.app.features.configurations.models import Configuration
from backend.app.features.documents.models import Document
from backend.app.features.jobs.models import Job
from backend.app.features.users.models import User
from backend.app.features.workspaces.models import Workspace


pytestmark = pytest.mark.asyncio


async def _seed_minimal_job_graph() -> tuple[str, str]:
    """Create minimal workspace/user/config/document/job rows and return (job_id, workspace_id)."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        # Workspace and user
        ts = uuid4().hex[:12]
        workspace = Workspace(name="Queue Test", slug=f"queue-{ts}")
        user = User(email=f"queue-user-{ts}@example.test", is_active=True)
        session.add_all([workspace, user])
        await session.flush()

        # Configuration
        configuration = Configuration(
            workspace_id=workspace.id,
            title="Test Configuration",
            version=1,
            is_active=False,
            activated_at=None,
            payload={},
        )
        session.add(configuration)
        await session.flush()

        # Document (minimal required fields)
        document = Document(
            workspace_id=workspace.id,
            original_filename="input.txt",
            content_type="text/plain",
            byte_size=5,
            sha256="deadbeef",
            stored_uri="uploads/test/input.txt",
            attributes={},
            uploaded_by_user_id=user.id,
            expires_at=datetime.now(tz=UTC) + timedelta(days=1),
            last_run_at=None,
        )
        session.add(document)
        await session.flush()

        # Job
        job = Job(
            workspace_id=workspace.id,
            configuration_id=configuration.id,
            status="created",
            created_by_user_id=user.id,
            input_document_id=document.id,
            metrics={},
            logs=[],
        )
        session.add(job)
        await session.flush()
        job_id = str(job.id)
        workspace_id = str(workspace.id)
        await session.commit()

    return job_id, workspace_id


async def test_claim_none_when_queue_empty() -> None:
    session_factory = get_sessionmaker()
    queue = SQLitePollingQueue(session_factory)
    message = await queue.claim()
    assert message is None


async def test_enqueue_claim_ack_updates_job_status() -> None:
    job_id, _ = await _seed_minimal_job_graph()

    session_factory = get_sessionmaker()
    queue = SQLitePollingQueue(session_factory)

    # Enqueue for processing
    enq = await queue.enqueue("jobs.run", {"job_id": job_id})
    assert enq.id == job_id
    assert enq.name == "jobs.run"
    assert int(enq.attempts) == 0

    # Claim transitions to running and increments attempts
    claimed = await queue.claim()
    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.name == "jobs.run"
    assert int(claimed.attempts) == 1

    # Ack transitions to succeeded
    await queue.ack(claimed)

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "succeeded"
        assert (job.metrics.get("queue") or {}).get("completed_at") is not None


async def test_enqueue_claim_fail_updates_job_status() -> None:
    job_id, _ = await _seed_minimal_job_graph()

    session_factory = get_sessionmaker()
    queue = SQLitePollingQueue(session_factory)

    await queue.enqueue("jobs.run", {"job_id": job_id})
    claimed = await queue.claim()
    assert claimed is not None

    await queue.fail(claimed, reason="boom")

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        qmeta = job.metrics.get("queue") or {}
        assert qmeta.get("last_error") == "boom"
        assert qmeta.get("failed_at") is not None
