from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

import pytest
from sqlalchemy import select

from backend.app import config as config_module
from backend.app import db as db_module
from backend.app.db import Base, get_engine, get_sessionmaker
from backend.app.models import Document
from backend.app.services.documents import (
    iter_expired_documents,
    purge_expired_documents,
    resolve_document_path,
    store_document,
)
from backend.app.maintenance import purge as purge_cli


@dataclass(slots=True)
class _StoredDocument:
    document: Document
    path: Path


def _create_document(
    db_session,
    *,
    filename: str,
    data: bytes,
    expires_delta: timedelta,
) -> _StoredDocument:
    document = store_document(
        db_session,
        original_filename=filename,
        content_type="application/octet-stream",
        data=data,
    )
    new_expiry = datetime.now(timezone.utc) + expires_delta
    document.expires_at = new_expiry.isoformat()
    document.updated_at = datetime.now(timezone.utc).isoformat()
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    path = resolve_document_path(document)
    return _StoredDocument(document=document, path=path)


@contextmanager
def _configured_environment(database_url: str, documents_dir: Path) -> Iterator[None]:
    config_module.reset_settings_cache()
    db_module.reset_database_state()
    documents_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=get_engine())
    try:
        yield
    finally:
        config_module.reset_settings_cache()
        db_module.reset_database_state()


def test_iter_expired_documents_batches_and_limit(app_client) -> None:
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()

    with session_factory() as db_session:
        expired_old = _create_document(
            db_session,
            filename="old.bin",
            data=b"old",
            expires_delta=timedelta(days=-2),
        )
        expired_recent = _create_document(
            db_session,
            filename="recent.bin",
            data=b"recent",
            expires_delta=timedelta(days=-1),
        )
        _create_document(
            db_session,
            filename="future.bin",
            data=b"future",
            expires_delta=timedelta(days=5),
        )

        batches = list(iter_expired_documents(db_session, batch_size=1))
        assert [[doc.document_id for doc in batch] for batch in batches] == [
            [expired_old.document.document_id],
            [expired_recent.document.document_id],
        ]

        limited_batches = list(iter_expired_documents(db_session, batch_size=5, limit=1))
        assert sum(len(batch) for batch in limited_batches) == 1
        assert limited_batches[0][0].document_id == expired_old.document.document_id


def test_purge_expired_documents_deletes_files(app_client) -> None:
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()

    with session_factory() as seed_session:
        expired_old = _create_document(
            seed_session,
            filename="delete-old.bin",
            data=b"delete-old",
            expires_delta=timedelta(days=-3),
        )
        expired_recent = _create_document(
            seed_session,
            filename="delete-recent.bin",
            data=b"delete-recent",
            expires_delta=timedelta(days=-1),
        )
        _create_document(
            seed_session,
            filename="keep.bin",
            data=b"keep",
            expires_delta=timedelta(days=10),
        )

    with session_factory() as purge_session:
        summary = purge_expired_documents(
            purge_session,
            batch_size=1,
        )

    assert summary.dry_run is False
    assert summary.processed_count == 2
    assert summary.missing_files == 0
    assert summary.bytes_reclaimed == expired_old.document.byte_size + expired_recent.document.byte_size
    assert [detail.document_id for detail in summary.documents] == [
        expired_old.document.document_id,
        expired_recent.document.document_id,
    ]

    assert not expired_old.path.exists()
    assert not expired_recent.path.exists()

    with session_factory() as verify_session:
        old_row = verify_session.get(Document, expired_old.document.document_id)
        assert old_row is not None
        assert old_row.deleted_at is not None
        assert old_row.deleted_by == "maintenance:purge_expired_documents"
        assert old_row.delete_reason == "expired_document_purge"

        recent_row = verify_session.get(Document, expired_recent.document.document_id)
        assert recent_row is not None
        assert recent_row.deleted_at is not None

        remaining = verify_session.scalars(
            select(Document).where(Document.deleted_at.is_(None))
        ).all()
        assert all(row.document_id != expired_old.document.document_id for row in remaining)
        assert all(row.document_id != expired_recent.document.document_id for row in remaining)


def test_purge_expired_documents_respects_limit(app_client) -> None:
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()

    with session_factory() as seed_session:
        expired_old = _create_document(
            seed_session,
            filename="limit-old.bin",
            data=b"limit-old",
            expires_delta=timedelta(days=-2),
        )
        expired_recent = _create_document(
            seed_session,
            filename="limit-recent.bin",
            data=b"limit-recent",
            expires_delta=timedelta(days=-1),
        )

    with session_factory() as purge_session:
        summary = purge_expired_documents(purge_session, limit=1)

    assert summary.processed_count == 1
    assert summary.documents[0].document_id == expired_old.document.document_id

    with session_factory() as verify_session:
        old_row = verify_session.get(Document, expired_old.document.document_id)
        assert old_row is not None and old_row.deleted_at is not None
        recent_row = verify_session.get(Document, expired_recent.document.document_id)
        assert recent_row is not None and recent_row.deleted_at is None


def test_purge_expired_documents_handles_missing_files(app_client) -> None:
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()

    with session_factory() as seed_session:
        expired_doc = _create_document(
            seed_session,
            filename="missing.bin",
            data=b"missing",
            expires_delta=timedelta(days=-1),
        )

    expired_doc.path.unlink()

    with session_factory() as purge_session:
        summary = purge_expired_documents(purge_session)

    assert summary.processed_count == 1
    assert summary.missing_files == 1
    assert summary.bytes_reclaimed == 0
    assert summary.documents[0].missing_before_delete is True

    with session_factory() as verify_session:
        row = verify_session.get(Document, expired_doc.document.document_id)
        assert row is not None
        assert row.deleted_at is not None


def test_purge_expired_documents_dry_run_leaves_state_untouched(app_client) -> None:
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()

    with session_factory() as seed_session:
        expired_doc = _create_document(
            seed_session,
            filename="dry-run.bin",
            data=b"dry-run",
            expires_delta=timedelta(days=-1),
        )

    with session_factory() as purge_session:
        summary = purge_expired_documents(purge_session, dry_run=True)

    assert summary.dry_run is True
    assert summary.processed_count == 1
    assert summary.bytes_reclaimed == expired_doc.document.byte_size
    assert summary.missing_files == 0
    assert summary.documents[0].document_id == expired_doc.document.document_id

    assert expired_doc.path.exists()

    with session_factory() as verify_session:
        row = verify_session.get(Document, expired_doc.document.document_id)
        assert row is not None
        assert row.deleted_at is None


def test_purge_cli_dry_run_reports_summary(tmp_path, monkeypatch, capsys) -> None:
    documents_dir = tmp_path / "documents"
    db_path = tmp_path / "ade.sqlite"
    database_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("ADE_DATABASE_URL", database_url)
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))

    with _configured_environment(database_url, documents_dir):
        from sqlalchemy import select

        session_factory = get_sessionmaker()
        with session_factory() as db_session:
            expired_doc = _create_document(
                db_session,
                filename="cli-dry.bin",
                data=b"cli-dry",
                expires_delta=timedelta(days=-1),
            )

        exit_code = purge_cli.main(["--dry-run"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Dry run" in captured.out
        assert expired_doc.document.document_id in captured.out

        with session_factory() as verify_session:
            row = verify_session.get(Document, expired_doc.document.document_id)
            assert row is not None
            assert row.deleted_at is None

    monkeypatch.delenv("ADE_DATABASE_URL", raising=False)
    monkeypatch.delenv("ADE_DOCUMENTS_DIR", raising=False)


def test_purge_cli_executes_purge(tmp_path, monkeypatch) -> None:
    documents_dir = tmp_path / "documents"
    db_path = tmp_path / "ade.sqlite"
    database_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("ADE_DATABASE_URL", database_url)
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))

    with _configured_environment(database_url, documents_dir):
        session_factory = get_sessionmaker()
        with session_factory() as db_session:
            expired_doc = _create_document(
                db_session,
                filename="cli-run.bin",
                data=b"cli-run",
                expires_delta=timedelta(days=-1),
            )

        exit_code = purge_cli.main([])
        assert exit_code == 0
        assert not expired_doc.path.exists()

        with session_factory() as verify_session:
            row = verify_session.get(Document, expired_doc.document.document_id)
            assert row is not None
            assert row.deleted_at is not None

    monkeypatch.delenv("ADE_DATABASE_URL", raising=False)
    monkeypatch.delenv("ADE_DOCUMENTS_DIR", raising=False)


def test_automatic_purge_scheduler_removes_expired_documents(
    app_client_factory,
    tmp_path,
    monkeypatch,
) -> None:
    documents_dir = tmp_path / "documents"
    db_path = tmp_path / "ade.sqlite"
    database_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("ADE_PURGE_SCHEDULE_ENABLED", "true")
    monkeypatch.setenv("ADE_PURGE_SCHEDULE_INTERVAL_SECONDS", "1")

    try:
        with app_client_factory(database_url, documents_dir):
            session_factory = get_sessionmaker()
            with session_factory() as db_session:
                expired_doc = _create_document(
                    db_session,
                    filename="auto.bin",
                    data=b"auto",
                    expires_delta=timedelta(days=-1),
                )

            assert expired_doc.path.exists()

            time.sleep(2)

            assert not expired_doc.path.exists()

            with session_factory() as verify_session:
                row = verify_session.get(Document, expired_doc.document.document_id)
                assert row is not None
                assert row.deleted_at is not None
    finally:
        monkeypatch.delenv("ADE_PURGE_SCHEDULE_ENABLED", raising=False)
        monkeypatch.delenv("ADE_PURGE_SCHEDULE_INTERVAL_SECONDS", raising=False)
