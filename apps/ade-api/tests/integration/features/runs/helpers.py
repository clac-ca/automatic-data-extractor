from __future__ import annotations

from pathlib import Path

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.service import RunsService
from ade_api.infra.storage import workspace_config_root, workspace_documents_root
from ade_api.models import (
    Configuration,
    ConfigurationStatus,
    Document,
    DocumentSource,
    Workspace,
)
from ade_api.settings import Settings


def build_runs_service(
    session,
    tmp_path: Path,
    *,
    safe_mode: bool = False,
) -> tuple[RunsService, Configuration, Document, Settings]:
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

    doc_storage = DocumentStorage(workspace_documents_root(settings, workspace.id))
    document_id = generate_uuid7()
    stored_uri = doc_storage.make_stored_uri(str(document_id))
    document_path = doc_storage.path_for(stored_uri)
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_text("name\nAlice\n", encoding="utf-8")

    document = Document(
        id=document_id,
        workspace_id=workspace.id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=document_path.stat().st_size,
        sha256="deadbeef",
        stored_uri=stored_uri,
        attributes={},
        source=DocumentSource.MANUAL_UPLOAD,
        expires_at=utc_now(),
    )
    session.add(document)
    session.commit()

    service = RunsService(
        session=session,
        settings=settings,
    )

    return service, configuration, document, settings
