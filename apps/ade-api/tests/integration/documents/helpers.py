"""Shared helpers for document integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ade_api.core.security.hashing import hash_password
from ade_api.db import generate_uuid7
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


async def build_documents_fixture(session):
    workspace = Workspace(name="Workspace", slug=f"ws-{uuid4().hex[:6]}")
    uploader = User(
        id=generate_uuid7(),
        email="uploader@example.com",
        hashed_password=hash_password("uploader-password"),
        display_name="Uploader One",
        is_active=True,
    )
    colleague = User(
        id=generate_uuid7(),
        email="colleague@example.com",
        hashed_password=hash_password("colleague-password"),
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


async def ensure_configuration(session, workspace_id):
    """Create minimal configuration row to satisfy run foreign keys."""

    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Test Config",
        status=ConfigurationStatus.ACTIVE,
    )
    session.add(configuration)
    await session.flush()

    return configuration.id


async def build_tag_filter_fixture(session):
    workspace = Workspace(name="Tagged Workspace", slug=f"ws-tags-{uuid4().hex[:6]}")
    uploader = User(
        id=generate_uuid7(),
        email="tagger@example.com",
        hashed_password=hash_password("tagger-password"),
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


async def seed_failed_run(session, *, workspace_id, document_id, uploader_id):
    now = datetime.now(tz=UTC)
    configuration_id = await ensure_configuration(session, workspace_id)
    build = Build(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        fingerprint="fingerprint",
        status=BuildStatus.READY,
        created_at=now - timedelta(minutes=15),
    )
    session.add(build)
    await session.flush()
    run = Run(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        build_id=build.id,
        submitted_by_user_id=uploader_id,
        status=RunStatus.FAILED,
        input_document_id=document_id,
        created_at=now - timedelta(minutes=10),
        started_at=now - timedelta(minutes=5),
        completed_at=now - timedelta(minutes=1),
        cancelled_at=None,
        error_message="Request failed with status 404",
    )
    session.add(run)
    await session.flush()
    return run
