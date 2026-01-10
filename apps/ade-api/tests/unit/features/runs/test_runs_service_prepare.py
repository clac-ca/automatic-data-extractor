from pathlib import Path

import pytest
from sqlalchemy import select

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.features.runs.exceptions import RunQueueFullError
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.models import Document, DocumentSource, DocumentStatus, Run, RunStatus

from tests.unit.features.runs.helpers import build_runs_service


def test_prepare_run_creates_queued_run(session, tmp_path: Path) -> None:
    service, configuration, document, _settings = build_runs_service(
        session,
        tmp_path,
    )

    options = RunCreateOptions(input_document_id=str(document.id))
    run = service.prepare_run(configuration_id=configuration.id, options=options)

    assert run.status is RunStatus.QUEUED
    assert run.engine_spec == str(_settings.engine_spec)
    assert run.deps_digest.startswith("sha256:")
    assert run.input_document_id == document.id
    assert run.input_sheet_names is None
    assert run.run_options is not None
    assert run.run_options.get("input_document_id") == str(document.id)


def test_prepare_run_rejects_when_queue_is_full(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, _settings = build_runs_service(
        session,
        tmp_path,
        queue_size=1,
    )

    options = RunCreateOptions(input_document_id=str(document.id))
    service.prepare_run(configuration_id=configuration.id, options=options)

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
    session.commit()

    with pytest.raises(RunQueueFullError):
        service.prepare_run(
            configuration_id=configuration.id,
            options=RunCreateOptions(input_document_id=str(second_document.id)),
        )


def test_enqueue_pending_runs_for_configuration_queues_uploaded_document(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, _settings = build_runs_service(
        session,
        tmp_path,
    )

    queued = service.enqueue_pending_runs_for_configuration(
        configuration_id=configuration.id,
    )
    assert queued == 1

    result = session.execute(select(Run).where(Run.input_document_id == document.id))
    runs = result.scalars().all()
    assert len(runs) == 1
    assert runs[0].configuration_id == configuration.id
    assert runs[0].status is RunStatus.QUEUED

    second = service.enqueue_pending_runs_for_configuration(
        configuration_id=configuration.id,
    )
    assert second == 0
