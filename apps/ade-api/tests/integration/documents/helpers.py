"""Shared helpers for document integration tests."""

from __future__ import annotations

import anyio
from datetime import UTC, datetime, timedelta
import unicodedata
from uuid import uuid4

from ade_api.core.security.hashing import hash_password
from ade_api.common.ids import generate_uuid7
from ade_api.models import (
    Configuration,
    ConfigurationStatus,
    File,
    FileKind,
    FileTag,
    FileVersion,
    FileVersionOrigin,
    Run,
    RunStatus,
    User,
    Workspace,
)


async def _flush(session) -> None:
    await anyio.to_thread.run_sync(session.flush)


def _build_name_key(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name)
    collapsed = " ".join(normalized.split())
    return collapsed.casefold()


async def _create_document_file(
    session,
    *,
    workspace_id,
    name: str,
    uploader_id,
    content_type: str,
    byte_size: int,
    sha256: str,
    expires_at: datetime,
    tags: list[str] | None = None,
    attributes: dict | None = None,
) -> tuple[File, FileVersion]:
    file_id = generate_uuid7()
    version_id = generate_uuid7()
    name_key = _build_name_key(name)
    blob_name = f"{workspace_id}/files/{file_id}"

    document = File(
        id=file_id,
        workspace_id=workspace_id,
        kind=FileKind.DOCUMENT,
        doc_no=None,
        name=name,
        name_key=name_key,
        blob_name=blob_name,
        parent_file_id=None,
        attributes=attributes or {},
        uploaded_by_user_id=uploader_id,
        expires_at=expires_at,
        comment_count=0,
        version=1,
    )

    version = FileVersion(
        id=version_id,
        file_id=file_id,
        version_no=1,
        origin=FileVersionOrigin.UPLOADED,
        created_by_user_id=uploader_id,
        sha256=sha256,
        byte_size=byte_size,
        content_type=content_type,
        filename_at_upload=name,
        blob_version_id="v1",
    )

    document.current_version = version
    document.versions.append(version)
    if tags:
        document.tags.extend([FileTag(file_id=file_id, tag=tag) for tag in tags])

    session.add_all([document, version])
    await _flush(session)
    return document, version


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
    await _flush(session)

    now = datetime.now(tz=UTC)
    expires = now + timedelta(days=30)

    processed, processed_version = await _create_document_file(
        session,
        workspace_id=workspace.id,
        name="alpha-report.pdf",
        uploader_id=uploader.id,
        content_type="application/pdf",
        byte_size=512,
        sha256="a" * 64,
        expires_at=expires,
        tags=["finance"],
    )

    uploaded, _uploaded_version = await _create_document_file(
        session,
        workspace_id=workspace.id,
        name="zeta-draft.docx",
        uploader_id=colleague.id,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        byte_size=128,
        sha256="b" * 64,
        expires_at=expires,
    )

    configuration_id = await ensure_configuration(session, workspace.id)
    run = Run(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        configuration_id=configuration_id,
        submitted_by_user_id=uploader.id,
        status=RunStatus.SUCCEEDED,
        input_file_version_id=processed_version.id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:2e1cfa82b035c26cbbbdae632cea070514eb8b773f616aaeaf668e2f0be8f10d",
        created_at=now - timedelta(hours=2),
        started_at=now - timedelta(hours=1, minutes=30),
        completed_at=now - timedelta(hours=1),
    )
    processed.last_run_id = run.id
    session.add(run)
    await _flush(session)

    return workspace, uploader, colleague, processed, uploaded


async def ensure_configuration(session, workspace_id):
    """Create minimal configuration row to satisfy run foreign keys."""

    existing = session.query(Configuration).filter(
        Configuration.workspace_id == workspace_id,
        Configuration.status == ConfigurationStatus.ACTIVE,
    ).first()
    if existing is not None:
        return existing.id

    configuration = Configuration(
        workspace_id=workspace_id,
        display_name="Test Config",
        status=ConfigurationStatus.ACTIVE,
    )
    session.add(configuration)
    await _flush(session)

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
    await _flush(session)

    now = datetime.now(tz=UTC)
    expires = now + timedelta(days=30)

    doc_all, _ = await _create_document_file(
        session,
        workspace_id=workspace.id,
        name="alpha.csv",
        uploader_id=uploader.id,
        content_type="text/csv",
        byte_size=200,
        sha256="c" * 64,
        expires_at=expires,
        tags=["finance", "priority"],
    )

    doc_finance, _ = await _create_document_file(
        session,
        workspace_id=workspace.id,
        name="bravo.csv",
        uploader_id=uploader.id,
        content_type="text/csv",
        byte_size=201,
        sha256="d" * 64,
        expires_at=expires,
        tags=["finance"],
    )

    doc_priority, _ = await _create_document_file(
        session,
        workspace_id=workspace.id,
        name="charlie.csv",
        uploader_id=uploader.id,
        content_type="text/csv",
        byte_size=202,
        sha256="e" * 64,
        expires_at=expires,
        tags=["priority"],
    )

    doc_empty, _ = await _create_document_file(
        session,
        workspace_id=workspace.id,
        name="delta.csv",
        uploader_id=uploader.id,
        content_type="text/csv",
        byte_size=203,
        sha256="f" * 64,
        expires_at=expires,
    )

    return workspace, uploader, doc_all, doc_finance, doc_priority, doc_empty


async def seed_failed_run(session, *, workspace_id, document_id, uploader_id):
    now = datetime.now(tz=UTC)
    configuration_id = await ensure_configuration(session, workspace_id)
    document = session.get(File, document_id)
    if document is None or document.current_version_id is None:
        raise RuntimeError("Document is missing or has no current version for run seeding.")
    run = Run(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        configuration_id=configuration_id,
        submitted_by_user_id=uploader_id,
        status=RunStatus.FAILED,
        input_file_version_id=document.current_version_id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:2e1cfa82b035c26cbbbdae632cea070514eb8b773f616aaeaf668e2f0be8f10d",
        created_at=now - timedelta(minutes=10),
        started_at=now - timedelta(minutes=5),
        completed_at=now - timedelta(minutes=1),
        error_message="Request failed with status 404",
    )
    document.last_run_id = run.id
    session.add(run)
    await _flush(session)
    return run
