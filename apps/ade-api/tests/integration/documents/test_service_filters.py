from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ade_api.common.sorting import resolve_sort
from ade_api.db import generate_uuid7
from ade_api.features.documents.filters import DocumentFilters
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_api.models import (
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentSource,
    DocumentStatus,
    DocumentTag,
    Run,
    RunStatus,
    User,
    Workspace,
)

pytestmark = pytest.mark.asyncio


async def _build_documents_fixture(session):
    workspace = Workspace(name="Workspace", slug=f"ws-{uuid4().hex[:6]}")
    uploader = User(
        id=generate_uuid7(),
        email="uploader@example.com",
        display_name="Uploader One",
        is_active=True,
    )
    colleague = User(
        id=generate_uuid7(),
        email="colleague@example.com",
        display_name="Colleague Two",
        is_active=True,
    )
    session.add_all([workspace, uploader, colleague])
    await session.flush()

    now = datetime.now(tz=UTC)
    expires = now + timedelta(days=30)

    processed = Document(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        original_filename="alpha-report.pdf",
        content_type="application/pdf",
        byte_size=512,
        sha256="a" * 64,
        stored_uri="alpha-report",
        attributes={},
        uploaded_by_user_id=uploader.id,
        status=DocumentStatus.PROCESSED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=expires,
        last_run_at=now - timedelta(days=1),
    )
    processed.tags.append(DocumentTag(document_id=processed.id, tag="finance"))

    uploaded = Document(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        original_filename="zeta-draft.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        byte_size=128,
        sha256="b" * 64,
        stored_uri="zeta-draft",
        attributes={},
        uploaded_by_user_id=colleague.id,
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=expires,
        last_run_at=None,
    )

    session.add_all([processed, uploaded])
    await session.flush()

    return workspace, uploader, colleague, processed, uploaded


async def _ensure_configuration(session, workspace_id):
    """Create minimal configuration row to satisfy run foreign keys."""

    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Test Config",
        status=ConfigurationStatus.ACTIVE,
    )
    session.add(configuration)
    await session.flush()

    return configuration.id


async def test_list_documents_applies_filters_and_sorting(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

    service = DocumentsService(session=session, settings=settings)

    filters = DocumentFilters(
        status_in={DocumentStatus.PROCESSED},
        tags_in={"finance"},
        uploader="me",
        q="Uploader",
    )
    order_by_recent = resolve_sort(
        ["-created_at"],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=True,
        order_by=order_by_recent,
        filters=filters,
        actor=uploader,
    )

    assert result.total == 1
    assert [item.id for item in result.items] == [processed.id]

    # Sorting by name ascending should place the draft before the report.
    name_order = resolve_sort(
        ["name"],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    name_sorted = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=name_order,
        filters=DocumentFilters(),
        actor=uploader,
    )
    assert [item.id for item in name_sorted.items] == [processed.id, uploaded.id]


async def test_last_run_filters_include_nulls_in_upper_bound(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

    service = DocumentsService(session=session, settings=settings)

    filters = DocumentFilters(last_run_to=datetime.now(tz=UTC))
    order_by_default = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by_default,
        filters=filters,
        actor=uploader,
    )

    returned_ids = {item.id for item in result.items}
    assert uploaded.id in returned_ids  # null last_run_at treated as "never"
    assert processed.id in returned_ids


async def test_sorting_last_run_places_nulls_last(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

    service = DocumentsService(session=session, settings=settings)

    order_by_last_run = resolve_sort(
        ["-last_run_at"],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by_last_run,
        filters=DocumentFilters(),
        actor=uploader,
    )

    assert [item.id for item in result.items] == [processed.id, uploaded.id]


async def test_list_documents_includes_last_run_summary(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

    now = datetime.now(tz=UTC)
    configuration_id = await _ensure_configuration(session, workspace.id)
    run = Run(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration_id,
        submitted_by_user_id=uploader.id,
        status=RunStatus.FAILED,
        attempt=1,
        retry_of_run_id=None,
        input_document_id=processed.id,
        trace_id=None,
        artifact_uri=None,
        output_uri=None,
        logs_uri=None,
        created_at=now - timedelta(minutes=10),
        started_at=now - timedelta(minutes=5),
        finished_at=now - timedelta(minutes=1),
        cancelled_at=None,
        error_message="Request failed with status 404",
    )
    session.add(run)
    await session.flush()

    service = DocumentsService(session=session, settings=settings)
    order_by = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    result = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=25,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(),
        actor=uploader,
    )

    processed_record = next(item for item in result.items if item.id == processed.id)
    assert processed_record.last_run is not None
    assert processed_record.last_run.run_id == run.id
    assert processed_record.last_run.status == RunStatus.FAILED
    assert processed_record.last_run.message == "Request failed with status 404"
    assert processed_record.last_run.run_at == run.finished_at

    uploaded_record = next(item for item in result.items if item.id == uploaded.id)
    assert uploaded_record.last_run is None
