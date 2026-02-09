from pathlib import Path

import pytest
from sqlalchemy import select

from ade_api.features.configs.exceptions import ConfigEngineDependencyMissingError
from ade_api.features.runs.exceptions import RunSafeModeEnabledError
from ade_api.features.runs.schemas import (
    RunBatchCreateOptions,
    RunCreateOptions,
    RunCreateOptionsBase,
)
from ade_db.models import Run, RunStatus
from tests.api.integration.features.runs.helpers import build_runs_service


def test_prepare_run_creates_queued_run(session, tmp_path: Path) -> None:
    service, configuration, document, _settings = build_runs_service(
        session,
        tmp_path,
    )

    options = RunCreateOptions(input_document_id=str(document.id))
    run = service.prepare_run(configuration_id=configuration.id, options=options)

    assert run.status is RunStatus.QUEUED
    assert run.deps_digest.startswith("sha256:")
    assert run.input_file_version_id == document.current_version_id
    assert run.input_sheet_names is None
    assert run.run_options is not None
    assert run.run_options.get("input_document_id") == str(document.id)


def test_prepare_run_blocked_when_safe_mode_enabled(session, tmp_path: Path) -> None:
    service, configuration, document, _settings = build_runs_service(
        session,
        tmp_path,
        safe_mode=True,
    )

    options = RunCreateOptions(input_document_id=str(document.id))
    with pytest.raises(RunSafeModeEnabledError):
        service.prepare_run(configuration_id=configuration.id, options=options)


def test_enqueue_pending_runs_for_configuration_queues_uploaded_document(
    session,
    tmp_path: Path,
) -> None:
    service, configuration, document, _settings = build_runs_service(
        session,
        tmp_path,
    )

    queued = service.enqueue_pending_runs_for_configuration(
        configuration_id=configuration.id,
    )
    assert queued == 1

    result = session.execute(
        select(Run).where(Run.input_file_version_id == document.current_version_id)
    )
    runs = result.scalars().all()
    assert len(runs) == 1
    assert runs[0].configuration_id == configuration.id
    assert runs[0].status is RunStatus.QUEUED

    second = service.enqueue_pending_runs_for_configuration(
        configuration_id=configuration.id,
    )
    assert second == 0


def test_prepare_run_requires_engine_dependency_manifest(session, tmp_path: Path) -> None:
    service, configuration, document, settings = build_runs_service(session, tmp_path)
    pyproject_path = (
        Path(settings.configs_dir)
        / str(configuration.workspace_id)
        / "config_packages"
        / str(configuration.id)
        / "pyproject.toml"
    )
    pyproject_path.write_text(
        "[project]\nname = \"ade-config\"\nversion = \"0.0.0\"\n",
        encoding="utf-8",
    )

    options = RunCreateOptions(input_document_id=str(document.id))
    with pytest.raises(ConfigEngineDependencyMissingError):
        service.prepare_run(configuration_id=configuration.id, options=options)


def test_prepare_run_for_workspace_accepts_run_options_base(session, tmp_path: Path) -> None:
    service, configuration, document, _settings = build_runs_service(session, tmp_path)

    run = service.prepare_run_for_workspace(
        workspace_id=configuration.workspace_id,
        input_document_id=document.id,
        configuration_id=None,
        options=RunCreateOptionsBase(active_sheet_only=True),
    )

    assert run.status is RunStatus.QUEUED
    assert run.input_file_version_id == document.current_version_id
    assert run.input_sheet_names is None
    assert run.run_options == {
        "operation": "process",
        "dry_run": False,
        "active_sheet_only": True,
        "input_document_id": str(document.id),
    }


def test_prepare_runs_batch_accepts_string_operation(session, tmp_path: Path) -> None:
    service, configuration, document, _settings = build_runs_service(session, tmp_path)

    runs = service.prepare_runs_batch(
        configuration_id=configuration.id,
        document_ids=[document.id],
        options=RunBatchCreateOptions(operation="process"),
    )

    assert len(runs) == 1
    assert runs[0].status is RunStatus.QUEUED
