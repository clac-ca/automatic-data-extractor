from pathlib import Path

import pytest
from sqlalchemy import select

from ade_api.common.time import utc_now
from ade_api.common.ids import generate_uuid7
from ade_api.features.runs.exceptions import RunQueueFullError
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.documents.storage import DocumentStorage
from ade_api.infra.storage import workspace_documents_root
from ade_api.models import Document, DocumentSource, DocumentStatus, Run, RunStatus

from tests.unit.features.runs.helpers import build_runs_service


@pytest.mark.asyncio()
async def test_prepare_run_emits_queued_event(session, tmp_path: Path) -> None:
    service, configuration, document, fake_builds, _ = await build_runs_service(
        session,
        tmp_path,
    )

    options = RunCreateOptions(input_document_id=str(document.id))
    run = await service.prepare_run(configuration_id=configuration.id, options=options)

    assert run.status is RunStatus.QUEUED
    assert fake_builds.force_calls == []
    assert run.build_id is None
    assert run.input_document_id == document.id
    assert run.input_sheet_names is None
    assert run.run_options is not None
    assert run.run_options.get("input_document_id") == str(document.id)

    events, _ = await service.get_run_events(run_id=run.id, limit=5)
    assert events and events[0]["event"] == "run.queued"
    queued_options = events[0].get("data", {}).get("options") or {}
    assert queued_options.get("input_document_id") == str(document.id)


@pytest.mark.asyncio()
async def test_prepare_run_rejects_when_queue_is_full(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, _fake_builds, settings = await build_runs_service(
        session,
        tmp_path,
    )
    settings.queue_size = 1

    options = RunCreateOptions(input_document_id=str(document.id))
    await service.prepare_run(configuration_id=configuration.id, options=options)

    second_document = Document(
        id=generate_uuid7(),
        workspace_id=configuration.workspace_id,
        original_filename="second.csv",
        content_type="text/csv",
        byte_size=12,
        sha256="deadbeef",
        stored_uri="documents/second.csv",
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add(second_document)
    await session.commit()

    with pytest.raises(RunQueueFullError):
        await service.prepare_run(
            configuration_id=configuration.id,
            options=RunCreateOptions(input_document_id=str(second_document.id)),
        )


@pytest.mark.asyncio()
async def test_enqueue_pending_runs_for_configuration_queues_uploaded_document(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, _fake_builds, _ = await build_runs_service(
        session,
        tmp_path,
    )

    queued = await service.enqueue_pending_runs_for_configuration(
        configuration_id=configuration.id,
    )
    assert queued == 1

    result = await session.execute(select(Run).where(Run.input_document_id == document.id))
    runs = result.scalars().all()
    assert len(runs) == 1
    assert runs[0].configuration_id == configuration.id
    assert runs[0].status is RunStatus.QUEUED

    second = await service.enqueue_pending_runs_for_configuration(
        configuration_id=configuration.id,
    )
    assert second == 0


@pytest.mark.asyncio()
async def test_complete_run_backfills_pending_documents(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, _fake_builds, settings = await build_runs_service(
        session,
        tmp_path,
    )
    settings.queue_size = 1

    doc_storage = DocumentStorage(workspace_documents_root(settings, configuration.workspace_id))
    second_id = generate_uuid7()
    stored_uri = doc_storage.make_stored_uri(str(second_id))
    document_path = doc_storage.path_for(stored_uri)
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_text("name\nBob\n", encoding="utf-8")

    second_document = Document(
        id=second_id,
        workspace_id=configuration.workspace_id,
        original_filename="second.csv",
        content_type="text/csv",
        byte_size=document_path.stat().st_size,
        sha256="beadfeed",
        stored_uri=stored_uri,
        attributes={},
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add(second_document)
    await session.commit()

    options = RunCreateOptions(input_document_id=str(document.id))
    run = await service.prepare_run(configuration_id=configuration.id, options=options)
    await service._complete_run(run, status=RunStatus.SUCCEEDED, exit_code=0)

    result = await session.execute(select(Run).where(Run.input_document_id == second_document.id))
    runs = result.scalars().all()
    assert len(runs) == 1
    assert runs[0].status is RunStatus.QUEUED
