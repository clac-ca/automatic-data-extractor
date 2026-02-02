from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ade_api.common.ids import generate_uuid7
from ade_db.models import (
    Configuration,
    ConfigurationStatus,
    File,
    FileKind,
    FileVersion,
    FileVersionOrigin,
    Run,
    RunStatus,
    Workspace,
)


def _create_configuration(session: Session) -> tuple[Workspace, Configuration]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    session.flush()

    configuration_id = generate_uuid7()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",  # minimal metadata for FK relations
        status=ConfigurationStatus.ACTIVE,
        content_digest="digest",
    )
    session.add(configuration)
    session.flush()
    return workspace, configuration


def test_run_defaults(session: Session) -> None:
    workspace, configuration = _create_configuration(session)

    file_id = generate_uuid7()
    version_id = generate_uuid7()
    document = File(
        id=file_id,
        workspace_id=workspace.id,
        kind=FileKind.INPUT,
        name="input.csv",
        name_key="input.csv",
        blob_name=f"{workspace.id}/files/{file_id}",
        attributes={},
        uploaded_by_user_id=None,
        comment_count=0,
    )
    version = FileVersion(
        id=version_id,
        file_id=file_id,
        version_no=1,
        origin=FileVersionOrigin.UPLOADED,
        created_by_user_id=None,
        sha256="deadbeef",
        byte_size=12,
        content_type="text/csv",
        filename_at_upload="input.csv",
        storage_version_id="v1",
    )
    document.current_version = version
    document.versions.append(version)
    session.add_all([document, version])
    session.flush()

    run = Run(
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        input_file_version_id=version.id,
        engine_spec="ade-engine @ git+https://github.com/clac-ca/ade-engine@main",
        deps_digest="sha256:2e1cfa82b035c26cbbbdae632cea070514eb8b773f616aaeaf668e2f0be8f10d",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    assert run.status is RunStatus.QUEUED
    assert run.input_file_version_id == version.id
    assert run.input_sheet_names is None
    assert isinstance(run.created_at, datetime)
    assert run.available_at is not None
    assert run.attempt_count == 0
    assert run.max_attempts == 3
    assert run.claimed_by is None
    assert run.claim_expires_at is None
    assert run.run_options is None
    assert run.started_at is None
    assert run.completed_at is None
