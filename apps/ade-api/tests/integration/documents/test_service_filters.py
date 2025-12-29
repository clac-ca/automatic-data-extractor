from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ade_api.common.sorting import resolve_sort
from ade_api.db import generate_uuid7
from ade_api.features.documents.filters import DocumentFilters
from ade_api.features.documents.service import DocumentsService
from ade_api.features.documents.sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from ade_api.models import (
    Build,
    BuildStatus,
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


async def _build_tag_filter_fixture(session):
    workspace = Workspace(name="Tagged Workspace", slug=f"ws-tags-{uuid4().hex[:6]}")
    uploader = User(
        id=generate_uuid7(),
        email="tagger@example.com",
        display_name="Tagger",
        is_active=True,
    )
    session.add_all([workspace, uploader])
    await session.flush()

    now = datetime.now(tz=UTC)
    expires = now + timedelta(days=30)

    doc_all = Document(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        original_filename="alpha.csv",
        content_type="text/csv",
        byte_size=200,
        sha256="c" * 64,
        stored_uri="alpha",
        attributes={},
        uploaded_by_user_id=uploader.id,
        status=DocumentStatus.PROCESSED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=expires,
        last_run_at=None,
    )
    doc_all.tags.extend(
        [
            DocumentTag(document_id=doc_all.id, tag="finance"),
            DocumentTag(document_id=doc_all.id, tag="priority"),
        ]
    )

    doc_finance = Document(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        original_filename="bravo.csv",
        content_type="text/csv",
        byte_size=201,
        sha256="d" * 64,
        stored_uri="bravo",
        attributes={},
        uploaded_by_user_id=uploader.id,
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=expires,
        last_run_at=None,
    )
    doc_finance.tags.append(DocumentTag(document_id=doc_finance.id, tag="finance"))

    doc_priority = Document(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        original_filename="charlie.csv",
        content_type="text/csv",
        byte_size=202,
        sha256="e" * 64,
        stored_uri="charlie",
        attributes={},
        uploaded_by_user_id=uploader.id,
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=expires,
        last_run_at=None,
    )
    doc_priority.tags.append(DocumentTag(document_id=doc_priority.id, tag="priority"))

    doc_empty = Document(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        original_filename="delta.csv",
        content_type="text/csv",
        byte_size=203,
        sha256="f" * 64,
        stored_uri="delta",
        attributes={},
        uploaded_by_user_id=uploader.id,
        status=DocumentStatus.UPLOADED,
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=expires,
        last_run_at=None,
    )

    session.add_all([doc_all, doc_finance, doc_priority, doc_empty])
    await session.flush()

    return workspace, uploader, doc_all, doc_finance, doc_priority, doc_empty


async def test_list_documents_applies_filters_and_sorting(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

    service = DocumentsService(session=session, settings=settings)

    filters = DocumentFilters(
        status_in={DocumentStatus.PROCESSED},
        tags={"finance"},
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


async def test_list_documents_includes_last_run_message(session, settings) -> None:
    workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

    now = datetime.now(tz=UTC)
    configuration_id = await _ensure_configuration(session, workspace.id)
    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration_id,
        fingerprint="fingerprint",
        status=BuildStatus.READY,
        created_at=now - timedelta(minutes=15),
    )
    session.add(build)
    await session.flush()
    run = Run(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration_id,
        build_id=build.id,
        submitted_by_user_id=uploader.id,
        status=RunStatus.FAILED,
        input_document_id=processed.id,
        created_at=now - timedelta(minutes=10),
        started_at=now - timedelta(minutes=5),
        completed_at=now - timedelta(minutes=1),
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
    assert processed_record.last_run.run_at == run.completed_at

    uploaded_record = next(item for item in result.items if item.id == uploaded.id)
    assert uploaded_record.last_run is None


async def test_tag_filters_any_all_not_empty(session, settings) -> None:
    workspace, uploader, doc_all, doc_finance, doc_priority, doc_empty = await _build_tag_filter_fixture(
        session
    )

    service = DocumentsService(session=session, settings=settings)
    order_by = resolve_sort(
        [],
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )

    any_match = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(tags={"finance", "priority"}),
        actor=uploader,
    )
    any_ids = {item.id for item in any_match.items}
    assert any_ids == {doc_all.id, doc_finance.id, doc_priority.id}

    all_match = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(tags={"finance", "priority"}, tags_match="all"),
        actor=uploader,
    )
    assert {item.id for item in all_match.items} == {doc_all.id}

    not_match = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(tags_not={"priority"}),
        actor=uploader,
    )
    not_ids = {item.id for item in not_match.items}
    assert doc_all.id not in not_ids
    assert doc_priority.id not in not_ids
    assert doc_finance.id in not_ids
    assert doc_empty.id in not_ids

    empty_match = await service.list_documents(
        workspace_id=workspace.id,
        page=1,
        page_size=50,
        include_total=False,
        order_by=order_by,
        filters=DocumentFilters(tags_empty=True),
        actor=uploader,
    )
    assert {item.id for item in empty_match.items} == {doc_empty.id}
