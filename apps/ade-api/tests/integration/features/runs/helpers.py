from __future__ import annotations

import io
from pathlib import Path

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.features.runs.service import RunsService
from ade_api.infra.storage import build_storage_adapter, workspace_config_root
from ade_api.models import (
    Configuration,
    ConfigurationStatus,
    File,
    FileKind,
    FileVersion,
    FileVersionOrigin,
    Workspace,
)
from ade_api.settings import Settings


def build_runs_service(
    session,
    tmp_path: Path,
    *,
    safe_mode: bool = False,
) -> tuple[RunsService, Configuration, File, Settings]:
    data_root = tmp_path / "data"
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir(parents=True, exist_ok=True)
    (engine_dir / "pyproject.toml").write_text(
        "[project]\nname = \"ade-engine\"\nversion = \"0.0.0\"\n",
        encoding="utf-8",
    )

    settings = Settings(
        _env_file=None,
        data_dir=data_root,
        safe_mode=safe_mode,
        engine_spec=str(engine_dir),
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_require_versioning=False,
        blob_create_container_on_startup=True,
    )

    workspace = Workspace(name="Test Workspace", slug=f"ws-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    session.flush()

    configuration = Configuration(
        workspace_id=workspace.id,
        display_name="Demo Config",
        status=ConfigurationStatus.ACTIVE,
        content_digest="digest",
    )
    session.add(configuration)
    session.flush()

    config_root = workspace_config_root(settings, workspace.id, configuration.id)
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "pyproject.toml").write_text(
        "[project]\nname = \"ade-config\"\nversion = \"0.0.0\"\n",
        encoding="utf-8",
    )

    document_id = generate_uuid7()
    blob_name = f"{workspace.id}/files/{document_id}"
    storage = build_storage_adapter(settings)
    stored = storage.write(blob_name, io.BytesIO(b"name\nAlice\n"))

    document = File(
        id=document_id,
        workspace_id=workspace.id,
        kind=FileKind.DOCUMENT,
        doc_no=None,
        name="input.csv",
        name_key="input.csv",
        blob_name=blob_name,
        attributes={},
        uploaded_by_user_id=None,
        expires_at=utc_now(),
        comment_count=0,
        version=1,
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
        blob_version_id=stored.version_id or stored.sha256,
    )
    document.current_version = version
    document.versions.append(version)
    session.add_all([document, version])
    session.commit()

    service = RunsService(
        session=session,
        settings=settings,
    )

    return service, configuration, document, settings
