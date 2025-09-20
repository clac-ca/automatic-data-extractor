from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MethodType
import time

import pytest


from backend.app import config as config_module
from backend.app import db as db_module
from backend.app.db import Base, get_engine, get_sessionmaker
from backend.app.models import Event, Document
from sqlalchemy import select

from backend.app.services.documents import (
    DocumentFileMissingError,
    ExpiredDocumentPurgeSummary,
    iter_expired_documents,
    purge_expired_documents,
    resolve_document_path,
    store_document,
)
from backend.app.services.maintenance_status import (
    get_auto_purge_status,
    record_auto_purge_failure,
    record_auto_purge_success,
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


def _bulk_create_expired_documents(
    db_session,
    *,
    documents_dir: Path,
    count: int,
) -> None:
    now = datetime.now(timezone.utc)
    created_at = now.isoformat()
    expires_at = (now - timedelta(days=1)).isoformat()

    documents_dir.mkdir(parents=True, exist_ok=True)

    chunk_size = 200
    chunk: list[Document] = []
    for index in range(count):
        document_id = f"BULK{index:022d}"
        stored_uri = f"uploads/bulk/{index:06d}.bin"
        target_path = documents_dir / stored_uri
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"x")
        chunk.append(
            Document(
                document_id=document_id,
                original_filename=f"bulk-{index}.bin",
                content_type="application/octet-stream",
                byte_size=1,
                sha256=f"sha256:{index:064x}",
                stored_uri=stored_uri,
                metadata_={},
                expires_at=expires_at,
                created_at=created_at,
                updated_at=created_at,
            )
        )
        if len(chunk) == chunk_size:
            db_session.bulk_save_objects(chunk)
            chunk.clear()

    if chunk:
        db_session.bulk_save_objects(chunk)

    db_session.commit()


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


def test_iter_expired_documents_streams_without_materialising(app_client) -> None:
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()

    class FakeScalarResult:
        def __init__(self, batches):
            self._batches = [list(batch) for batch in batches]
            self.fetch_sizes: list[int] = []
            self.closed = False

        def fetchmany(self, size):
            self.fetch_sizes.append(size)
            if not self._batches:
                return []
            return self._batches.pop(0)

        def close(self):
            self.closed = True

    with session_factory() as db_session:
        fake_result = FakeScalarResult([["expired-1", "expired-2"], ["expired-3"]])

        def fake_scalars(self, statement):
            fake_scalars.calls += 1
            return fake_result

        fake_scalars.calls = 0
        original_scalars = db_session.scalars
        db_session.scalars = MethodType(fake_scalars, db_session)
        try:
            batches = list(iter_expired_documents(db_session, batch_size=2))
        finally:
            db_session.scalars = original_scalars

    assert batches == [["expired-1", "expired-2"], ["expired-3"]]
    assert fake_scalars.calls == 1
    assert fake_result.fetch_sizes == [2, 2, 2]
    assert fake_result.closed is True


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

        events = verify_session.scalars(
            select(Event).where(
                Event.event_type == "document.deleted",
                Event.entity_id.in_(
                    [
                        expired_old.document.document_id,
                        expired_recent.document.document_id,
                    ]
                ),
            )
        ).all()
        assert len(events) == 2
        assert all(event.source == "scheduler" for event in events)
        assert all(
            event.actor_label == "maintenance:purge_expired_documents" for event in events
        )
        assert all(event.payload["delete_reason"] == "expired_document_purge" for event in events)

        remaining = verify_session.scalars(
            select(Document).where(Document.deleted_at.is_(None))
        ).all()
        assert all(row.document_id != expired_old.document.document_id for row in remaining)
        assert all(row.document_id != expired_recent.document.document_id for row in remaining)


def test_purge_expired_documents_streams_large_batches(app_client) -> None:
    client, _, documents_dir = app_client
    del client
    session_factory = get_sessionmaker()

    total_documents = 2049
    batch_size = 128

    with session_factory() as seed_session:
        _bulk_create_expired_documents(
            seed_session,
            documents_dir=documents_dir,
            count=total_documents,
        )

    with session_factory() as purge_session:
        summary = purge_expired_documents(
            purge_session,
            batch_size=batch_size,
            dry_run=True,
        )

    assert summary.dry_run is True
    assert summary.processed_count == total_documents
    assert summary.bytes_reclaimed == total_documents
    assert len(summary.documents) == total_documents
    assert summary.documents[0].document_id == "BULK0000000000000000000000"
    assert summary.documents[-1].document_id == f"BULK{total_documents - 1:022d}"


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


def test_purge_expired_documents_raises_when_file_missing(app_client) -> None:
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
        with pytest.raises(DocumentFileMissingError):
            purge_expired_documents(purge_session)

    with session_factory() as verify_session:
        row = verify_session.get(Document, expired_doc.document.document_id)
        assert row is not None
        assert row.deleted_at is None


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
    assert summary.documents[0].document_id == expired_doc.document.document_id

    assert expired_doc.path.exists()

    with session_factory() as verify_session:
        row = verify_session.get(Document, expired_doc.document.document_id)
        assert row is not None
        assert row.deleted_at is None


def test_auto_purge_status_records_successful_run(app_client) -> None:
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()

    summary = ExpiredDocumentPurgeSummary(
        dry_run=False,
        processed_count=5,
        bytes_reclaimed=2048,
    )
    started_at = "2024-01-01T00:00:00+00:00"
    completed_at = "2024-01-01T00:05:00+00:00"

    with session_factory() as db_session:
        record_auto_purge_success(
            db_session,
            summary=summary,
            started_at=started_at,
            completed_at=completed_at,
            interval_seconds=900,
        )
        db_session.commit()

    with session_factory() as verify_session:
        status = get_auto_purge_status(verify_session)
        assert status is not None
        assert status["status"] == "succeeded"
        assert status["dry_run"] is False
        assert status["processed_count"] == 5
        assert status["bytes_reclaimed"] == 2048
        assert status["started_at"] == started_at
        assert status["completed_at"] == completed_at
        assert status["interval_seconds"] == 900
        assert status["error"] is None
        assert "missing_files" not in status
        assert "recorded_at" in status


def test_auto_purge_status_records_failure(app_client) -> None:
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()

    started_at = "2024-02-01T00:00:00+00:00"

    with session_factory() as db_session:
        record_auto_purge_failure(
            db_session,
            started_at=started_at,
            completed_at=None,
            interval_seconds=1200,
            error="boom",
        )
        db_session.commit()

    with session_factory() as verify_session:
        status = get_auto_purge_status(verify_session)
        assert status is not None
        assert status["status"] == "failed"
        assert status["dry_run"] is None
        assert status["processed_count"] is None
        assert status["bytes_reclaimed"] is None
        assert status["started_at"] == started_at
        assert status["completed_at"] is None
        assert status["interval_seconds"] == 1200
        assert status["error"] == "boom"
        assert "missing_files" not in status
        assert "recorded_at" in status


def test_purge_cli_dry_run_reports_summary(tmp_path, monkeypatch, capsys) -> None:
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
