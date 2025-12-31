"""Document streaming tests."""

from __future__ import annotations

import io

import pytest
from fastapi import UploadFile

from ade_api.features.documents.exceptions import DocumentFileMissingError
from ade_api.features.documents.service import DocumentsService
from ade_api.infra.storage import workspace_documents_root
from ade_api.models import Document, User
from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


async def test_stream_document_handles_missing_file_mid_stream(
    seed_identity,
    session,
    settings: Settings,
) -> None:
    """Document streaming should surface a domain error when the file disappears."""

    service = DocumentsService(session=session, settings=settings)
    workspace_id = seed_identity.workspace_id

    member = await session.get(User, seed_identity.member.id)
    assert member is not None

    upload = UploadFile(
        filename="race.txt",
        file=io.BytesIO(b"race"),
    )
    record = await service.create_document(
        workspace_id=workspace_id,
        upload=upload,
        metadata=None,
        expires_at=None,
        actor=member,
    )

    _, stream = await service.stream_document(
        workspace_id=workspace_id,
        document_id=record.id,
    )

    stored_row = await session.get(Document, record.id)
    assert stored_row is not None
    stored_path = workspace_documents_root(settings, workspace_id) / stored_row.stored_uri
    stored_path.unlink()

    with pytest.raises(DocumentFileMissingError):
        async for _ in stream:
            pass
