from __future__ import annotations

from pathlib import Path

import pytest

from apps.api.app.features.configs.models import Configuration, ConfigurationStatus
from apps.api.app.features.documents.models import (
    Document,
    DocumentSource,
    DocumentStatus,
)
from apps.api.app.features.jobs.models import JobStatus
from apps.api.app.features.jobs.schemas import JobSubmissionRequest
from apps.api.app.features.jobs.service import JobsService
from apps.api.app.features.runs.models import RunStatus
from apps.api.app.features.runs.service import RunExecutionContext
from apps.api.app.features.workspaces.models import Workspace
from apps.api.app.settings import Settings
from apps.api.app.shared.core.ids import generate_ulid
from apps.api.app.shared.core.time import utc_now


class StubRunsService:
    """Minimal stub of the runs service for JobsService tests."""

    def __init__(self, jobs_dir: Path) -> None:
        self.jobs_dir = jobs_dir
        self.run_id = f"run_{generate_ulid()}"

    async def prepare_run(self, *, config_id: str, options, job_id: str, jobs_dir: Path):
        context = RunExecutionContext(
            run_id=self.run_id,
            configuration_id=generate_ulid(),
            workspace_id=generate_ulid(),
            config_id=config_id,
            venv_path=str(jobs_dir / "venv"),
            build_id=generate_ulid(),
            job_id=job_id,
            jobs_dir=str(jobs_dir),
        )
        run = type("Run", (), {"id": self.run_id})()
        return run, context

    async def run_to_completion(self, *, context, options):  # noqa: D401 - signature match
        return None

    async def get_run(self, run_id: str):  # noqa: D401 - signature match
        return type(
            "RunRecord",
            (),
            {
                "id": run_id,
                "status": RunStatus.SUCCEEDED,
                "started_at": utc_now(),
                "finished_at": utc_now(),
                "exit_code": 0,
                "error_message": None,
            },
        )()


@pytest.fixture()
async def jobs_service(tmp_path: Path, session):
    data_dir = tmp_path
    documents_dir = data_dir / "documents"
    jobs_dir = data_dir / "jobs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings().model_copy(
        update={
            "documents_dir": documents_dir,
            "jobs_dir": jobs_dir,
            "venvs_dir": data_dir / ".venv",
        }
    )

    workspace = Workspace(name="Acme", slug=f"acme-{generate_ulid().lower()}")
    session.add(workspace)
    await session.flush()

    configuration = Configuration(
        workspace_id=workspace.id,
        config_id=generate_ulid(),
        display_name="Runtime Config",
        status=ConfigurationStatus.ACTIVE,
        config_version=1,
        content_digest="digest",
    )
    session.add(configuration)

    stored_uri = "uploads/input.csv"
    source_path = documents_dir / stored_uri
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("a,b\n1,2\n", encoding="utf-8")

    document = Document(
        workspace_id=workspace.id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=source_path.stat().st_size,
        sha256="deadbeef",
        stored_uri=stored_uri,
        attributes={},
        uploaded_by_user_id=None,
        status=DocumentStatus.UPLOADED.value,
        source=DocumentSource.MANUAL_UPLOAD.value,
        expires_at=utc_now(),
    )
    document.id = generate_ulid()
    session.add(document)
    await session.commit()

    runs_stub = StubRunsService(jobs_dir)
    service = JobsService(session=session, settings=settings, runs_service=runs_stub)
    return {
        "service": service,
        "workspace": workspace,
        "configuration": configuration,
        "document": document,
        "settings": settings,
        "jobs_dir": jobs_dir,
    }


@pytest.mark.asyncio()
async def test_submit_job_copies_document_and_records_completion(jobs_service, session):
    service: JobsService = jobs_service["service"]
    configuration: Configuration = jobs_service["configuration"]
    document: Document = jobs_service["document"]
    jobs_dir: Path = jobs_service["jobs_dir"]

    payload = JobSubmissionRequest(
        input_document_id=document.id,
        config_version_id=configuration.config_id,
    )
    record = await service.submit_job(
        workspace_id=configuration.workspace_id,
        payload=payload,
        actor=None,
    )

    assert record.status == JobStatus.SUCCEEDED.value
    assert record.config_id == configuration.config_id
    assert record.input_documents[0].document_id == document.id

    job_input = jobs_dir / record.id / "input" / document.original_filename
    assert job_input.exists()

    refreshed_doc = await session.get(Document, document.id)
    assert refreshed_doc.last_run_at is not None


@pytest.mark.asyncio()
async def test_list_and_get_jobs(jobs_service, session):
    service: JobsService = jobs_service["service"]
    configuration: Configuration = jobs_service["configuration"]
    document: Document = jobs_service["document"]

    payload = JobSubmissionRequest(
        input_document_id=document.id,
        config_version_id=configuration.config_id,
    )
    record = await service.submit_job(
        workspace_id=configuration.workspace_id,
        payload=payload,
        actor=None,
    )

    jobs = await service.list_jobs(workspace_id=configuration.workspace_id)
    assert any(job.id == record.id for job in jobs)

    filtered = await service.list_jobs(
        workspace_id=configuration.workspace_id,
        input_document_id=document.id,
    )
    assert filtered and filtered[0].id == record.id

    fetched = await service.get_job(
        workspace_id=configuration.workspace_id,
        job_id=record.id,
    )
    assert fetched is not None
    assert fetched.id == record.id
