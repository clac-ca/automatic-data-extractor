from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from ade_api.common.ids import generate_uuid7
from ade_api.features.admin_settings.service import DEFAULT_SAFE_MODE_DETAIL
from ade_api.features.runs.service import RunsService
from ade_api.settings import Settings
from ade_db.models import (
    ApplicationSetting,
    Configuration,
    ConfigurationStatus,
    File,
    FileKind,
    FileVersion,
    FileVersionOrigin,
    Workspace,
)
from ade_storage import workspace_config_root
from ade_storage.base import StorageAdapter, StoredObject


class _InMemoryStorageAdapter(StorageAdapter):
    """Minimal storage adapter for run-preparation integration tests."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def check_connection(self) -> None:
        return

    def write(
        self,
        uri: str,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
    ) -> StoredObject:
        payload = stream.read()
        if max_bytes is not None and len(payload) > max_bytes:
            raise ValueError("payload exceeds max_bytes")
        digest = hashlib.sha256(payload).hexdigest()
        self._objects[uri] = payload
        return StoredObject(
            uri=uri,
            sha256=digest,
            byte_size=len(payload),
            version_id=digest,
        )

    def stream(
        self,
        uri: str,
        *,
        version_id: str | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        del version_id
        payload = self._objects[uri]
        for start in range(0, len(payload), chunk_size):
            yield payload[start : start + chunk_size]

    def stream_range(
        self,
        uri: str,
        *,
        start_offset: int = 0,
        version_id: str | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        del version_id
        payload = self._objects[uri][start_offset:]
        for start in range(0, len(payload), chunk_size):
            yield payload[start : start + chunk_size]

    def delete(self, uri: str, *, version_id: str | None = None) -> None:
        del version_id
        self._objects.pop(uri, None)


def build_runs_service(
    session,
    tmp_path: Path,
    *,
    safe_mode: bool = False,
) -> tuple[RunsService, Configuration, File, Settings]:
    data_root = tmp_path / "data"

    settings = Settings(
        _env_file=None,
        data_dir=data_root,
        safe_mode=safe_mode,
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        blob_versioning_mode="off",
        secret_key="test-secret-key-for-tests-please-change",
    )

    workspace = Workspace(name="Test Workspace", slug=f"ws-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    session.flush()

    configuration = Configuration(
        workspace_id=workspace.id,
        display_name="Demo Config",
        status=ConfigurationStatus.ACTIVE,
        published_digest="digest",
    )
    session.add(configuration)
    session.flush()

    config_root = workspace_config_root(settings, workspace.id, configuration.id)
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "pyproject.toml").write_text(
        (
            "[project]\n"
            "name = \"ade-config\"\n"
            "version = \"0.0.0\"\n"
            "dependencies = [\"ade-engine\"]\n"
        ),
        encoding="utf-8",
    )

    document_id = generate_uuid7()
    blob_name = f"{workspace.id}/files/{document_id}"
    storage = _InMemoryStorageAdapter()
    stored = storage.write(blob_name, io.BytesIO(b"name\nAlice\n"))

    document = File(
        id=document_id,
        workspace_id=workspace.id,
        kind=FileKind.INPUT,
        name="input.csv",
        name_key="input.csv",
        blob_name=blob_name,
        attributes={},
        uploaded_by_user_id=None,
        comment_count=0,
    )
    version = FileVersion(
        id=generate_uuid7(),
        file_id=document_id,
        version_no=1,
        origin=FileVersionOrigin.UPLOADED,
        created_by_user_id=None,
        sha256=stored.sha256,
        byte_size=stored.byte_size,
        content_type="text/csv",
        filename_at_upload="input.csv",
        storage_version_id=stored.version_id or stored.sha256,
    )
    document.current_version = version
    document.versions.append(version)
    session.add_all([document, version])
    if safe_mode:
        record = session.get(ApplicationSetting, 1)
        payload = {
            "safe_mode": {
                "enabled": True,
                "detail": DEFAULT_SAFE_MODE_DETAIL,
            },
            "auth": {
                "mode": "password_only",
                "password": {
                    "reset_enabled": True,
                    "mfa_required": False,
                    "complexity": {
                        "min_length": 12,
                        "require_uppercase": False,
                        "require_lowercase": False,
                        "require_number": False,
                        "require_symbol": False,
                    },
                    "lockout": {
                        "max_attempts": 5,
                        "duration_seconds": 300,
                    },
                },
                "identity_provider": {
                    "jit_provisioning_enabled": True,
                },
            },
        }
        if record is None:
            session.add(
                ApplicationSetting(
                    id=1,
                    schema_version=2,
                    data=payload,
                    revision=1,
                )
            )
        else:
            record.schema_version = 2
            record.data = payload
            record.revision = int(record.revision) + 1
    session.commit()

    service = RunsService(
        session=session,
        settings=settings,
        blob_storage=storage,
    )

    return service, configuration, document, settings
