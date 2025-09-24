"""Service layer for document metadata operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO

from fastapi.concurrency import run_in_threadpool

from ...core.service import BaseService, ServiceContext
from ...db.mixins import generate_ulid
from ..events.recorder import persist_event
from ..jobs.exceptions import JobNotFoundError
from ..jobs.models import Job
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    InvalidDocumentExpirationError,
)
from .models import Document
from .repository import DocumentsRepository
from .schemas import DocumentRecord

_CHUNK_SIZE = 1024 * 1024
_UPLOAD_SUBDIR = "uploads"


@dataclass(slots=True)
class DocumentUploadPayload:
    """Structured representation of an incoming document upload."""

    filename: str | None
    content_type: str | None
    stream: BinaryIO


@dataclass(slots=True)
class DocumentDownload:
    """Prepared artefact for streaming a stored document from disk."""

    record: DocumentRecord
    path: Path

    @property
    def document_id(self) -> str:
        return self.record.document_id

    @property
    def filename(self) -> str:
        return self.record.original_filename

    @property
    def content_type(self) -> str | None:
        return self.record.content_type

    @property
    def byte_size(self) -> int:
        return self.record.byte_size

    @property
    def sha256(self) -> str:
        return self.record.sha256

    @property
    def stored_uri(self) -> str:
        return self.record.stored_uri


class DocumentsService(BaseService):
    """Expose helpers for managing document metadata and storage."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("DocumentsService requires a database session")
        self._repository = DocumentsRepository(self.session)

    async def create_document(
        self,
        *,
        upload: DocumentUploadPayload,
        expires_at: str | None = None,
        produced_by_job_id: str | None = None,
    ) -> DocumentRecord:
        """Persist ``upload`` metadata and stored bytes then emit an event."""

        if self.session is None:
            raise RuntimeError("DocumentsService requires a database session")

        if produced_by_job_id is not None:
            await self._ensure_job_exists(produced_by_job_id)

        document_id = generate_ulid()
        stored_uri = f"{_UPLOAD_SUBDIR}/{document_id}"
        documents_dir = Path(self.settings.documents_dir)
        destination = (documents_dir / stored_uri).resolve()

        digest, size = await self._persist_stream(
            upload.stream,
            destination,
            max_bytes=self.settings.max_upload_bytes,
        )

        expiration = self._resolve_expiration(expires_at)

        document = Document(
            id=document_id,
            original_filename=self._normalise_filename(upload.filename),
            content_type=self._normalise_content_type(upload.content_type),
            byte_size=size,
            sha256=digest,
            stored_uri=stored_uri,
            metadata_={},
            expires_at=expiration,
            produced_by_job_id=produced_by_job_id,
        )

        session = self.session
        session.add(document)
        try:
            await session.flush()
            record = DocumentRecord.model_validate(document)
            metadata = {"entity_type": "document", "entity_id": record.document_id}
            await self.publish_event(
                "document.uploaded",
                self._build_upload_event_payload(record),
                metadata=metadata,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            await self._remove_stored_file(destination)
            raise

        await session.refresh(document)
        return DocumentRecord.model_validate(document)

    async def list_documents(
        self,
        *,
        limit: int,
        offset: int,
        produced_by_job_id: str | None = None,
        include_deleted: bool = False,
    ) -> list[DocumentRecord]:
        """Return documents ordered by recency."""

        documents = await self._repository.list_documents(
            include_deleted=include_deleted,
            produced_by_job_id=produced_by_job_id,
            limit=limit,
            offset=offset,
        )
        records = [DocumentRecord.model_validate(document) for document in documents]

        payload: dict[str, Any] = {
            "count": len(records),
            "limit": limit,
            "offset": offset,
        }
        if produced_by_job_id is not None:
            payload["produced_by_job_id"] = produced_by_job_id

        metadata: dict[str, Any] = {"entity_type": "document_collection"}
        workspace = self.current_workspace
        workspace_id = None
        if workspace is not None:
            workspace_id = getattr(workspace, "workspace_id", None) or getattr(
                workspace, "id", None
            )
        metadata["entity_id"] = str(workspace_id) if workspace_id is not None else "global"

        await self.publish_event("documents.listed", payload, metadata=metadata)
        return records

    async def get_document(
        self,
        *,
        document_id: str,
        include_deleted: bool = False,
        emit_event: bool = True,
    ) -> DocumentRecord:
        """Return a single document by identifier."""

        document = await self._repository.get_document(document_id)
        if document is None or (document.deleted_at and not include_deleted):
            raise DocumentNotFoundError(document_id)

        record = DocumentRecord.model_validate(document)
        if emit_event:
            metadata = {"entity_type": "document", "entity_id": record.document_id}
            await self.publish_event(
                "document.viewed",
                {"document_id": record.document_id},
                metadata=metadata,
            )
        return record

    async def prepare_document_download(self, *, document_id: str) -> DocumentDownload:
        """Return the artefacts required to stream ``document_id`` from disk."""

        document = await self._repository.get_document(document_id)
        if document is None or document.deleted_at is not None:
            raise DocumentNotFoundError(document_id)

        record = DocumentRecord.model_validate(document)
        stored_path = await self._resolve_stored_file(
            stored_uri=record.stored_uri,
            document_id=record.document_id,
        )

        metadata = {"entity_type": "document", "entity_id": record.document_id}
        await self.publish_event(
            "document.downloaded",
            self._build_download_event_payload(record),
            metadata=metadata,
        )

        return DocumentDownload(record=record, path=stored_path)

    async def delete_document(
        self,
        *,
        document_id: str,
        reason: str | None = None,
    ) -> DocumentRecord:
        """Soft delete ``document_id`` while recording audit metadata."""

        if self.session is None:
            raise RuntimeError("DocumentsService requires a database session")

        document = await self._repository.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)

        stored_path = self._resolve_storage_path(stored_uri=document.stored_uri)

        if document.deleted_at is not None:
            if stored_path is not None:
                await self._remove_stored_file(stored_path)
            return DocumentRecord.model_validate(document)

        deleted_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        document.deleted_at = deleted_at
        document.deleted_by = self._resolve_actor_label()
        document.delete_reason = self._normalise_delete_reason(reason)

        session = self.session
        session.add(document)

        try:
            await session.flush()
            record = DocumentRecord.model_validate(document)
            metadata = {"entity_type": "document", "entity_id": record.document_id}
            await self.publish_event(
                "document.deleted",
                self._build_delete_event_payload(record),
                metadata=metadata,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        await session.refresh(document)
        if stored_path is not None:
            await self._remove_stored_file(stored_path)
        return DocumentRecord.model_validate(document)

    async def update_document_metadata(
        self,
        *,
        document_id: str,
        metadata: Mapping[str, Any] | None = None,
        event_type: str | None = None,
        event_payload: Mapping[str, Any] | None = None,
    ) -> DocumentRecord:
        """Merge ``metadata`` into the document and emit an audit event."""

        if self.session is None:
            raise RuntimeError("DocumentsService requires a database session")

        document = await self._repository.get_document(document_id)
        if document is None or document.deleted_at is not None:
            raise DocumentNotFoundError(document_id)

        (
            merged_metadata,
            changed_keys,
            removed_keys,
            metadata_updated,
        ) = self._merge_metadata(document.metadata_, metadata)
        if metadata_updated:
            document.metadata_ = merged_metadata

        event_name = self._normalise_event_type(event_type)
        if event_name is None and metadata_updated:
            event_name = "document.metadata.updated"

        if event_name is None and not metadata_updated:
            return DocumentRecord.model_validate(document)

        session = self.session
        session.add(document)

        try:
            await session.flush()
            record = DocumentRecord.model_validate(document)
            payload = self._build_metadata_update_event_payload(
                record=record,
                changed_keys=changed_keys,
                removed_keys=removed_keys,
                metadata_updated=metadata_updated,
                overrides=event_payload,
            )
            metadata_context = {
                "entity_type": "document",
                "entity_id": record.document_id,
            }
            if event_name is not None:
                await self.publish_event(
                    event_name,
                    payload,
                    metadata=metadata_context,
                )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        await session.refresh(document)
        return DocumentRecord.model_validate(document)

    async def _ensure_job_exists(self, job_id: str) -> None:
        if self.session is None:
            raise RuntimeError("DocumentsService requires a database session")

        job = await self.session.get(Job, job_id)
        if job is None:
            raise JobNotFoundError(job_id)

    async def _persist_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> None:
        if self.session is None:
            return

        await persist_event(
            self.session,
            name=name,
            payload=payload,
            metadata=metadata,
            correlation_id=self.correlation_id,
        )

    async def _persist_stream(
        self,
        stream: BinaryIO,
        destination: Path,
        *,
        max_bytes: int,
    ) -> tuple[str, int]:
        """Persist ``stream`` to ``destination`` returning the digest and byte size."""

        def _write() -> tuple[str, int]:
            try:
                stream.seek(0)
            except Exception:  # pragma: no cover - defensive best effort
                pass

            size = 0
            digest = sha256()
            destination.parent.mkdir(parents=True, exist_ok=True)

            try:
                with destination.open("wb") as buffer:
                    while True:
                        chunk = stream.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        prospective = size + len(chunk)
                        if prospective > max_bytes:
                            raise DocumentTooLargeError(
                                limit=max_bytes, received=prospective
                            )
                        buffer.write(chunk)
                        digest.update(chunk)
                        size = prospective
            except Exception:
                try:
                    destination.unlink(missing_ok=True)
                except Exception:  # pragma: no cover - cleanup best effort
                    pass
                raise

            return digest.hexdigest(), size

        return await run_in_threadpool(_write)

    async def _remove_stored_file(self, path: Path) -> None:
        """Remove ``path`` without raising if the file is absent."""

        def _remove() -> None:
            path.unlink(missing_ok=True)

        await run_in_threadpool(_remove)

    async def _resolve_stored_file(
        self, *, stored_uri: str, document_id: str
    ) -> Path:
        """Return the absolute path for ``stored_uri`` ensuring it exists."""

        documents_dir = Path(self.settings.documents_dir).resolve()

        def _resolve() -> Path:
            candidate = (documents_dir / stored_uri).resolve()
            try:
                candidate.relative_to(documents_dir)
            except ValueError as exc:  # pragma: no cover - defensive path handling
                raise DocumentFileMissingError(
                    document_id=document_id, stored_uri=stored_uri
                ) from exc
            if not candidate.is_file():
                raise DocumentFileMissingError(
                    document_id=document_id,
                    stored_uri=stored_uri,
                )
            return candidate

        try:
            return await run_in_threadpool(_resolve)
        except FileNotFoundError as exc:
            raise DocumentFileMissingError(
                document_id=document_id, stored_uri=stored_uri
            ) from exc

    def _resolve_storage_path(self, *, stored_uri: str) -> Path | None:
        """Return a safe absolute path for ``stored_uri`` even if missing."""

        documents_dir = Path(self.settings.documents_dir).resolve()
        try:
            candidate = (documents_dir / stored_uri).resolve()
        except FileNotFoundError:
            return None

        try:
            candidate.relative_to(documents_dir)
        except ValueError:
            return None
        return candidate

    def _resolve_expiration(self, override: str | None) -> str:
        """Return the ISO timestamp when the document should expire."""

        now = datetime.now(timezone.utc)
        if override is None:
            retention = self.settings.default_document_retention_days
            return (now + timedelta(days=retention)).isoformat(timespec="milliseconds")

        candidate = override.strip()
        if not candidate:
            raise InvalidDocumentExpirationError("expires_at must not be blank")
        if candidate.endswith(("Z", "z")):
            candidate = f"{candidate[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:  # pragma: no cover - error handling exercised in tests
            raise InvalidDocumentExpirationError(
                "expires_at must be a valid ISO 8601 timestamp"
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)

        if parsed <= now:
            raise InvalidDocumentExpirationError("expires_at must be in the future")

        return parsed.isoformat(timespec="milliseconds")

    @staticmethod
    def _normalise_filename(filename: str | None) -> str:
        if filename is None:
            return "upload"
        candidate = filename.strip()
        return candidate or "upload"

    @staticmethod
    def _normalise_content_type(content_type: str | None) -> str | None:
        if content_type is None:
            return None
        candidate = content_type.strip()
        return candidate or None

    @staticmethod
    def _build_upload_event_payload(record: DocumentRecord) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_id": record.document_id,
            "original_filename": record.original_filename,
            "byte_size": record.byte_size,
            "sha256": record.sha256,
            "stored_uri": record.stored_uri,
            "expires_at": record.expires_at,
        }
        if record.content_type is not None:
            payload["content_type"] = record.content_type
        if record.produced_by_job_id is not None:
            payload["produced_by_job_id"] = record.produced_by_job_id
        return payload

    @staticmethod
    def _build_download_event_payload(record: DocumentRecord) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_id": record.document_id,
            "original_filename": record.original_filename,
            "byte_size": record.byte_size,
            "sha256": record.sha256,
            "stored_uri": record.stored_uri,
        }
        if record.content_type is not None:
            payload["content_type"] = record.content_type
        if record.produced_by_job_id is not None:
            payload["produced_by_job_id"] = record.produced_by_job_id
        return payload

    def _resolve_actor_label(self) -> str | None:
        """Return the descriptive label for the actor performing the action."""

        user = self.current_user
        if user is not None:
            label = getattr(user, "email", None) or getattr(user, "id", None)
            return str(label) if label is not None else None

        service_account = self.current_service_account
        if service_account is not None:
            label = getattr(service_account, "display_name", None) or getattr(
                service_account, "name", None
            )
            return str(label) if label is not None else None

        return None

    @staticmethod
    def _normalise_delete_reason(reason: str | None) -> str | None:
        if reason is None:
            return None
        cleaned = reason.strip()
        return cleaned or None

    @staticmethod
    def _build_delete_event_payload(record: DocumentRecord) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_id": record.document_id,
            "original_filename": record.original_filename,
            "byte_size": record.byte_size,
            "sha256": record.sha256,
            "stored_uri": record.stored_uri,
            "expires_at": record.expires_at,
            "deleted_at": record.deleted_at,
        }
        if record.content_type is not None:
            payload["content_type"] = record.content_type
        if record.produced_by_job_id is not None:
            payload["produced_by_job_id"] = record.produced_by_job_id
        if record.delete_reason is not None:
            payload["delete_reason"] = record.delete_reason
        if record.deleted_by is not None:
            payload["deleted_by"] = record.deleted_by
        return payload

    @staticmethod
    def _merge_metadata(
        current: Mapping[str, Any] | None,
        updates: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any], set[str], set[str], bool]:
        baseline = dict(current or {})
        changed_keys: set[str] = set()
        removed_keys: set[str] = set()
        metadata_updated = False

        if updates is None:
            return baseline, changed_keys, removed_keys, metadata_updated

        for key, value in updates.items():
            key_str = str(key)
            if value is None:
                if key_str in baseline:
                    baseline.pop(key_str)
                    removed_keys.add(key_str)
                    metadata_updated = True
                continue

            existing = baseline.get(key_str)
            if existing != value:
                baseline[key_str] = value
                changed_keys.add(key_str)
                metadata_updated = True

        return baseline, changed_keys, removed_keys, metadata_updated

    @staticmethod
    def _build_metadata_update_event_payload(
        *,
        record: DocumentRecord,
        changed_keys: set[str],
        removed_keys: set[str],
        metadata_updated: bool,
        overrides: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"document_id": record.document_id}

        if metadata_updated:
            if changed_keys:
                payload["metadata"] = {
                    key: record.metadata[key]
                    for key in sorted(changed_keys)
                    if key in record.metadata
                }

            affected = changed_keys | removed_keys
            if affected:
                payload["changed_keys"] = sorted(affected)
            if removed_keys:
                payload["removed_keys"] = sorted(removed_keys)

        if overrides:
            payload.update(dict(overrides))

        return payload

    @staticmethod
    def _normalise_event_type(candidate: str | None) -> str | None:
        if candidate is None:
            return None
        cleaned = candidate.strip()
        return cleaned or None


__all__ = ["DocumentDownload", "DocumentUploadPayload", "DocumentsService"]
