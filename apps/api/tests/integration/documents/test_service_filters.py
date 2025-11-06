from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.api.app.shared.core.config import get_settings
from apps.api.app.shared.db import generate_ulid
from apps.api.app.shared.db.session import get_sessionmaker
from apps.api.app.features.documents.filtering import (
    DocumentFilters,
    DocumentSort,
    DocumentSortableField,
    DocumentSource,
    DocumentStatus,
)
from apps.api.app.features.documents.models import Document, DocumentTag
from apps.api.app.features.documents.service import DocumentsService
from apps.api.app.features.users.models import User
from apps.api.app.features.workspaces.models import Workspace


pytestmark = pytest.mark.asyncio


async def _build_documents_fixture(session):
    workspace = Workspace(name="Workspace", slug=f"ws-{uuid4().hex[:6]}")
    uploader = User(
        id=generate_ulid(),
        email="uploader@example.test",
        display_name="Uploader One",
        is_active=True,
    )
    colleague = User(
        id=generate_ulid(),
        email="colleague@example.test",
        display_name="Colleague Two",
        is_active=True,
    )
    session.add_all([workspace, uploader, colleague])
    await session.flush()

    now = datetime.now(tz=UTC)
    expires = now + timedelta(days=30)

    processed = Document(
        id=generate_ulid(),
        workspace_id=str(workspace.id),
        original_filename="alpha-report.pdf",
        content_type="application/pdf",
        byte_size=512,
        sha256="a" * 64,
        stored_uri="alpha-report",
        attributes={},
        uploaded_by_user_id=uploader.id,
        status=DocumentStatus.PROCESSED.value,
        source=DocumentSource.MANUAL_UPLOAD.value,
        expires_at=expires,
        last_run_at=now - timedelta(days=1),
    )
    processed.tags.append(DocumentTag(document_id=processed.id, tag="finance"))

    uploaded = Document(
        id=generate_ulid(),
        workspace_id=str(workspace.id),
        original_filename="zeta-draft.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        byte_size=128,
        sha256="b" * 64,
        stored_uri="zeta-draft",
        attributes={},
        uploaded_by_user_id=colleague.id,
        status=DocumentStatus.UPLOADED.value,
        source=DocumentSource.MANUAL_UPLOAD.value,
        expires_at=expires,
        last_run_at=None,
    )

    session.add_all([processed, uploaded])
    await session.flush()

    return workspace, uploader, colleague, processed, uploaded


async def test_list_documents_applies_filters_and_sorting() -> None:
    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

        service = DocumentsService(session=session, settings=settings)

        filters = DocumentFilters(
            status=[DocumentStatus.PROCESSED],
            tags=["finance"],
            uploader_me=True,
            q="Uploader",
        )
        result = await service.list_documents(
            workspace_id=str(workspace.id),
            page=1,
            per_page=50,
            include_total=True,
            filters=filters,
            sort=DocumentSort(field=DocumentSortableField.CREATED_AT, descending=True),
            actor=uploader,
        )

        assert result.total == 1
        assert [item.document_id for item in result.items] == [processed.id]

        # Sorting by name ascending should place the draft before the report.
        name_sorted = await service.list_documents(
            workspace_id=str(workspace.id),
            page=1,
            per_page=50,
            filters=DocumentFilters(),
            sort=DocumentSort(field=DocumentSortableField.NAME, descending=False),
            actor=uploader,
        )
        assert [item.document_id for item in name_sorted.items] == [processed.id, uploaded.id]


async def test_last_run_filters_include_nulls_in_upper_bound() -> None:
    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

        service = DocumentsService(session=session, settings=settings)

        filters = DocumentFilters(last_run_to=datetime.now(tz=UTC))
        result = await service.list_documents(
            workspace_id=str(workspace.id),
            page=1,
            per_page=50,
            filters=filters,
            sort=DocumentSort.parse(None),
            actor=uploader,
        )

        returned_ids = {item.document_id for item in result.items}
        assert uploaded.id in returned_ids  # null last_run_at treated as "never"
        assert processed.id in returned_ids


async def test_sorting_last_run_places_nulls_last() -> None:
    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        workspace, uploader, colleague, processed, uploaded = await _build_documents_fixture(session)

        service = DocumentsService(session=session, settings=settings)

        result = await service.list_documents(
            workspace_id=str(workspace.id),
            page=1,
            per_page=50,
            filters=DocumentFilters(),
            sort=DocumentSort(field=DocumentSortableField.LAST_RUN_AT, descending=True),
            actor=uploader,
        )

        assert [item.document_id for item in result.items] == [processed.id, uploaded.id]
