"""Document streaming tests."""

from __future__ import annotations

import io

import pytest
from fastapi import UploadFile

from ade_api.features.documents.exceptions import DocumentFileMissingError
from ade_api.features.documents.service import DocumentsService
from ade_api.infra.storage import build_storage_adapter
from ade_api.models import File, User
from ade_api.settings import Settings


def test_stream_document_handles_missing_file(
    seed_identity,
    db_session,
    settings: Settings,
) -> None:
    """Document streaming should surface a domain error when the file is missing."""

    storage = build_storage_adapter(settings)
    service = DocumentsService(session=db_session, settings=settings, storage=storage)
    workspace_id = seed_identity.workspace_id

    member = db_session.get(User, seed_identity.member.id)
    assert member is not None

    upload = UploadFile(
        filename="race.txt",
        file=io.BytesIO(b"race"),
    )
    plan = service.plan_upload(
        workspace_id=workspace_id,
        filename=upload.filename,
    )
    record = service.create_document(
        workspace_id=workspace_id,
        upload=upload,
        plan=plan,
        metadata=None,
        expires_at=None,
        actor=member,
    )

    stored_row = db_session.get(File, record.id)
    assert stored_row is not None
    storage.delete(stored_row.blob_name)

    with pytest.raises(DocumentFileMissingError):
        _, stream = service.stream_document(
            workspace_id=workspace_id,
            document_id=record.id,
        )
        for _ in stream:
            pass
