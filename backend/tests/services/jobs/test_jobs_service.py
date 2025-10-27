"""Job service tests for config version integration."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from backend.app.shared.core.config import get_settings
from backend.app.shared.db import generate_ulid
from backend.app.shared.db.session import get_sessionmaker
from backend.app.features.configs.service import ConfigFileService, ConfigService, ManifestService
from backend.app.features.configs.schemas import ManifestPatchRequest
from backend.app.features.documents.service import DocumentsService
from backend.app.features.jobs.exceptions import JobExecutionError
from backend.app.features.jobs.models import Job
from backend.app.features.jobs.service import JobsService
from backend.app.features.workspaces.models import Workspace
from backend.app.features.users.models import User


pytestmark = pytest.mark.asyncio


async def _create_published_config_version(
    session,
    *,
    workspace_id: str,
    actor_id: str,
    manifest_extras: dict[str, object] | None = None,
) -> str:
    config_service = ConfigService(session=session)
    file_service = ConfigFileService(session=session)
    manifest_service = ManifestService(session=session)

    config = await config_service.create_config(
        workspace_id=workspace_id,
        slug=f"jobs-config-{uuid4().hex[:8]}",
        title="Jobs Config",
        actor_id=actor_id,
    )

    await file_service.create_draft_file(
        workspace_id=workspace_id,
        config_id=config.config_id,
        path="columns/value.py",
        code="def transform(value):\n    return value\n",
        language="python",
    )

    manifest_update: dict[str, object] = {
        "columns": [
            {
                "key": "value",
                "label": "Value",
                "path": "columns/value.py",
                "ordinal": 1,
                "required": True,
                "enabled": True,
                "depends_on": [],
            }
        ],
    }
    if manifest_extras:
        manifest_update.update(manifest_extras)

    await manifest_service.patch_manifest(
        workspace_id=workspace_id,
        config_id=config.config_id,
        payload=ManifestPatchRequest(manifest=manifest_update),
    )

    published = await config_service.publish_draft(
        workspace_id=workspace_id,
        config_id=config.config_id,
        semver="1.0.0",
        message="Initial",
        actor_id=actor_id,
    )

    return published.config_version_id


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

        actor = SimpleNamespace(id=generate_ulid(), email="user@example.test")
        session.add(User(id=actor.id, email=actor.email, display_name="User 1"))
        await session.flush()

        documents_service = DocumentsService(session=session, settings=settings)
        upload = UploadFile(
            filename="input.txt",
            file=BytesIO(b"payload"),
            headers=Headers({"content-type": "text/plain"}),
        )
        document_record = await documents_service.create_document(
            workspace_id=str(workspace.id),
            upload=upload,
            actor=actor,
        )

        config_version_id = await _create_published_config_version(
            session,
            workspace_id=str(workspace.id),
            actor_id=actor.id,
            manifest_extras={
                "tables": [
                    {
                        "title": "Line Items",
                        "columns": ["description", "amount"],
                        "rows": [
                            {"description": "Item A", "amount": 10},
                            {"description": "Item B", "amount": 20},
                        ],
                    }
                ],
                "metrics": {"tables_produced": 1, "rows_processed": 2},
            },
        )

        jobs_service = JobsService(session=session, settings=settings)

        record = await jobs_service.submit_job(
            workspace_id=str(workspace.id),
            input_document_id=document_record.document_id,
            config_version_id=config_version_id,
            actor_id=actor.id,
        )

        assert record.status == "succeeded"
        assert record.metrics["tables_produced"] == 1
        assert record.run_key

        job = await session.get(Job, record.job_id)
        assert job is not None
        assert job.status == "succeeded"
        assert job.config_version_id == config_version_id
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

        actor = SimpleNamespace(id=generate_ulid(), email="user2@example.test")
        session.add(User(id=actor.id, email=actor.email, display_name="User 2"))
        await session.flush()

        documents_service = DocumentsService(session=session, settings=settings)
        upload = UploadFile(
            filename="input.txt",
            file=BytesIO(b"payload"),
            headers=Headers({"content-type": "text/plain"}),
        )
        document_record = await documents_service.create_document(
            workspace_id=str(workspace.id),
            upload=upload,
            actor=actor,
        )

        config_version_id = await _create_published_config_version(
            session,
            workspace_id=str(workspace.id),
            actor_id=actor.id,
            manifest_extras={"simulate_failure": True, "failure_message": "Boom"},
        )

        jobs_service = JobsService(session=session, settings=settings)

        with pytest.raises(JobExecutionError) as excinfo:
            await jobs_service.submit_job(
                workspace_id=str(workspace.id),
                input_document_id=document_record.document_id,
                config_version_id=config_version_id,
                actor_id=actor.id,
            )

        job_id = excinfo.value.job_id
        assert job_id

        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.metrics.get("error") == "Boom"
