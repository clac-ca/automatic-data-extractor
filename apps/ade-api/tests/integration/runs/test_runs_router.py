"""Integration coverage for the runs API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
import tomllib

import openpyxl
import pytest
from httpx import AsyncClient

from ade_api.features.builds.fingerprint import compute_build_fingerprint
from ade_api.features.builds.models import Build, BuildStatus
from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.features.configs.storage import compute_config_digest
from ade_api.features.documents.models import Document
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.models import Run, RunStatus
from ade_api.features.runs.schemas import RunCreateOptions
from ade_api.features.runs.service import RunExecutionContext, RunsService
from ade_api.features.system_settings.service import SafeModeService
from ade_api.features.workspaces.models import Workspace
from ade_api.settings import Settings, get_settings
from ade_api.shared.core.time import utc_now
from ade_api.shared.db.mixins import generate_ulid
from ade_api.shared.db.session import get_sessionmaker
from ade_api.storage_layout import (
    build_venv_marker_path,
    build_venv_path,
    workspace_config_root,
    workspace_documents_root,
)
from tests.utils import login
from ade_engine.schemas import AdeEvent

pytestmark = pytest.mark.asyncio

_SETTINGS = get_settings()
CSRF_COOKIE = _SETTINGS.session_csrf_cookie_name
_REPO_ROOT = Path(__file__).resolve().parents[5]
_ENGINE_PACKAGE = _REPO_ROOT / "apps" / "ade-engine"
_CONFIG_TEMPLATE = (
    _REPO_ROOT
    / "apps"
    / "ade-api"
    / "src"
    / "ade_api"
    / "templates"
    / "config_packages"
    / "default"
)


def _engine_version_hint(spec: str) -> str | None:
    """Best-effort version detection mirroring the builds service."""

    spec_path = Path(spec)
    if spec_path.exists() and spec_path.is_dir():
        pyproject = spec_path / "pyproject.toml"
        if pyproject.exists():
            try:
                parsed = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                return parsed.get("project", {}).get("version")
            except Exception:
                return None
    if "==" in spec:
        return spec.split("==", 1)[1]
    return None


async def _prepare_service(
    session,
    tmp_path: Path,
) -> tuple[RunsService, RunExecutionContext, Document]:
    """Create a runnable configuration and document for workspace runs tests."""

    settings = get_settings()
    workspace = Workspace(name="Workspace", slug=f"ws-{generate_ulid().lower()}")
    session.add(workspace)
    await session.flush()

    configuration_id = generate_ulid()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
        configuration_version=1,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()

    build_id = generate_ulid()
    venv_path = build_venv_path(settings, workspace.id, configuration.id, build_id)
    venv_path.mkdir(parents=True, exist_ok=True)
    config_root = workspace_config_root(settings, workspace.id, configuration.id)
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.0.1'\n",
        encoding="utf-8",
    )
    engine_version = _engine_version_hint(settings.engine_spec)
    digest = compute_config_digest(config_root)
    fingerprint = compute_build_fingerprint(
        config_digest=digest,
        engine_spec=settings.engine_spec,
        engine_version=engine_version,
        python_version=".".join(map(str, sys.version_info[:3])),
        python_bin=settings.python_bin,
        extra={},
    )

    marker = build_venv_marker_path(settings, workspace.id, configuration.id, build_id)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"build_id": build_id, "fingerprint": fingerprint}, indent=2),
        encoding="utf-8",
    )
    bin_dir = venv_path / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_name = "python.exe" if os.name == "nt" else "python"
    (bin_dir / python_name).write_text("", encoding="utf-8")

    build = Build(
        id=build_id,
        workspace_id=workspace.id,
        configuration_id=configuration.id,
        status=BuildStatus.ACTIVE,
        created_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
        exit_code=0,
        fingerprint=fingerprint,
        engine_spec=settings.engine_spec,
        engine_version=engine_version,
        python_version=".".join(map(str, sys.version_info[:3])),
        python_interpreter=settings.python_bin or sys.executable,
        config_digest=digest,
    )
    session.add(build)

    configuration.active_build_id = build_id  # type: ignore[attr-defined]
    configuration.active_build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
    configuration.active_build_fingerprint = fingerprint  # type: ignore[attr-defined]
    configuration.active_build_started_at = utc_now()  # type: ignore[attr-defined]
    configuration.active_build_finished_at = utc_now()  # type: ignore[attr-defined]
    configuration.build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
    configuration.engine_spec = settings.engine_spec  # type: ignore[attr-defined]
    configuration.engine_version = engine_version or "0.2.0"  # type: ignore[attr-defined]
    configuration.python_interpreter = settings.python_bin  # type: ignore[attr-defined]
    configuration.python_version = "3.12.1"  # type: ignore[attr-defined]
    configuration.last_build_finished_at = utc_now()  # type: ignore[attr-defined]
    configuration.last_build_id = build_id  # type: ignore[attr-defined]
    configuration.built_content_digest = digest  # type: ignore[attr-defined]
    configuration.content_digest = digest
    await session.flush()

    storage = DocumentStorage(workspace_documents_root(settings, workspace.id))
    document_id = generate_ulid()
    stored_uri = storage.make_stored_uri(document_id)
    source_path = storage.path_for(stored_uri)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("name\nAlice", encoding="utf-8")

    document = Document(
        id=document_id,
        workspace_id=workspace.id,
        original_filename="input.csv",
        content_type="text/csv",
        byte_size=source_path.stat().st_size,
        sha256="deadbeef",
        stored_uri=stored_uri,
        attributes={},
        uploaded_by_user_id=None,
        status="processed",
        expires_at=utc_now() + timedelta(days=30),
    )
    session.add(document)
    await session.commit()

    service = RunsService(session=session, settings=settings)
    run, context = await service.prepare_run(
        configuration_id=configuration.id,
        options=RunCreateOptions(input_document_id=document.id),
    )
    return service, context, document


async def _seed_configuration(
    *,
    settings: Settings,
    workspace_id: str,
    tmp_path: Path,
) -> str:
    """Insert a configuration and active build used to drive runs tests."""

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        config_id = generate_ulid()
        config = Configuration(
            id=config_id,
            workspace_id=workspace_id,
            display_name="Test Configuration",
            status=ConfigurationStatus.ACTIVE,
        )
        session.add(config)
        await session.flush()

        build_id = generate_ulid()
        venv_path = build_venv_path(settings, workspace_id, config.id, build_id)
        venv_path.mkdir(parents=True, exist_ok=True)
        config_root = workspace_config_root(settings, workspace_id, config.id)
        config_root.mkdir(parents=True, exist_ok=True)
        (config_root / "pyproject.toml").write_text(
            "[project]\nname='demo'\nversion='0.0.1'\n",
            encoding="utf-8",
        )
        digest = compute_config_digest(config_root)
        engine_version = _engine_version_hint(settings.engine_spec)
        fingerprint = compute_build_fingerprint(
            config_digest=digest,
            engine_spec=settings.engine_spec,
            engine_version=engine_version,
            python_version=".".join(map(str, sys.version_info[:3])),
            python_bin=settings.python_bin,
            extra={},
        )

        marker = build_venv_marker_path(settings, workspace_id, config.id, build_id)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            json.dumps({"build_id": build_id, "fingerprint": fingerprint}, indent=2),
            encoding="utf-8",
        )
        bin_dir = venv_path / ("Scripts" if os.name == "nt" else "bin")
        bin_dir.mkdir(parents=True, exist_ok=True)
        python_name = "python.exe" if os.name == "nt" else "python"
        (bin_dir / python_name).write_text("", encoding="utf-8")

        build = Build(
            id=build_id,
            workspace_id=workspace_id,
            configuration_id=config.id,
            status=BuildStatus.ACTIVE,
            created_at=utc_now(),
            started_at=utc_now(),
            finished_at=utc_now(),
            exit_code=0,
            fingerprint=fingerprint,
            engine_spec=settings.engine_spec,
            engine_version=engine_version,
            python_version=".".join(map(str, sys.version_info[:3])),
            python_interpreter=settings.python_bin or sys.executable,
            config_digest=digest,
        )
        session.add(build)

        config.active_build_id = build_id  # type: ignore[attr-defined]
        config.active_build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
        config.active_build_fingerprint = fingerprint  # type: ignore[attr-defined]
        config.active_build_started_at = utc_now()  # type: ignore[attr-defined]
        config.active_build_finished_at = utc_now()  # type: ignore[attr-defined]
        config.build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
        config.engine_spec = settings.engine_spec  # type: ignore[attr-defined]
        config.engine_version = engine_version or "0.2.0"  # type: ignore[attr-defined]
        config.python_interpreter = settings.python_bin  # type: ignore[attr-defined]
        config.python_version = "3.12.1"  # type: ignore[attr-defined]
        config.last_build_finished_at = utc_now()  # type: ignore[attr-defined]
        config.last_build_id = build_id  # type: ignore[attr-defined]
        config.built_content_digest = digest  # type: ignore[attr-defined]
        config.content_digest = digest
        await session.commit()
        return config.id


def _venv_executable(venv_path: Path, name: str) -> Path:
    """Return an executable path inside ``venv_path`` honoring platform layout."""

    bin_dir = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return venv_path / bin_dir / f"{name}{suffix}"


def _pip_install(pip_executable: Path, package: Path | str) -> None:
    """Install ``package`` into the runtime venv using pip."""

    env = os.environ.copy()
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    env.setdefault("PIP_ROOT_USER_ACTION", "ignore")
    subprocess.run([str(pip_executable), "install", str(package)], check=True, env=env)


async def _seed_real_configuration(
    *,
    settings: Settings,
    workspace_id: str,
    tmp_path: Path,
) -> str:
    """Create a configuration with a fully provisioned runtime environment."""

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        config_id = generate_ulid()
        config = Configuration(
            id=config_id,
            workspace_id=workspace_id,
            display_name="Real Config",
            status=ConfigurationStatus.ACTIVE,
            configuration_version=1,
            content_digest="integration-test",
        )
        session.add(config)
        await session.flush()

        build_id = generate_ulid()
        venv_path = build_venv_path(settings, workspace_id, config.id, build_id)
        if venv_path.exists():
            shutil.rmtree(venv_path)
        venv_path.parent.mkdir(parents=True, exist_ok=True)
        python_bin = settings.python_bin
        resolved_python_bin = str(Path(python_bin).resolve()) if python_bin else None
        venv_interpreter = resolved_python_bin or sys.executable
        subprocess.run([venv_interpreter, "-m", "venv", str(venv_path)], check=True)

        pip_exe = _venv_executable(venv_path, "pip")
        _pip_install(pip_exe, _ENGINE_PACKAGE)
        config_src = workspace_config_root(settings, workspace_id, config.id)
        shutil.copytree(_CONFIG_TEMPLATE, config_src, dirs_exist_ok=True)
        _pip_install(pip_exe, config_src)

        python_exe = _venv_executable(venv_path, "python")
        engine_version = _engine_version_hint(settings.engine_spec)
        try:
            python_version = subprocess.check_output(
                [resolved_python_bin or sys.executable, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
                text=True,
            ).strip()
        except Exception:
            python_version = None
        python_interpreter = resolved_python_bin
        digest = compute_config_digest(config_src)
        now = utc_now()
        config.build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
        config.engine_spec = settings.engine_spec  # type: ignore[attr-defined]
        config.engine_version = engine_version  # type: ignore[attr-defined]
        config.python_version = python_version  # type: ignore[attr-defined]
        config.python_interpreter = python_interpreter  # type: ignore[attr-defined]
        config.last_build_started_at = now  # type: ignore[attr-defined]
        config.last_build_finished_at = now  # type: ignore[attr-defined]
        config.built_configuration_version = config.configuration_version  # type: ignore[attr-defined]
        config.content_digest = digest  # type: ignore[attr-defined]
        config.built_content_digest = digest  # type: ignore[attr-defined]
        config.last_build_id = build_id  # type: ignore[attr-defined]
        fingerprint = compute_build_fingerprint(
            config_digest=digest,
            engine_spec=settings.engine_spec,
            engine_version=engine_version,
            python_version=python_version,
            python_bin=resolved_python_bin,
            extra={},
        )
        marker = build_venv_marker_path(settings, workspace_id, config.id, build_id)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            json.dumps({"build_id": build_id, "fingerprint": fingerprint}, indent=2),
            encoding="utf-8",
        )
        build = Build(
            id=build_id,
            workspace_id=workspace_id,
            configuration_id=config.id,
            status=BuildStatus.ACTIVE,
            created_at=now,
            started_at=now,
            finished_at=now,
            exit_code=0,
            fingerprint=fingerprint,
            engine_spec=settings.engine_spec,
            engine_version=engine_version,
            python_version=python_version,
            python_interpreter=python_interpreter,
            config_digest=digest,
        )
        session.add(build)
        config.active_build_id = build_id  # type: ignore[attr-defined]
        config.active_build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
        config.active_build_fingerprint = fingerprint  # type: ignore[attr-defined]
        config.active_build_started_at = now  # type: ignore[attr-defined]
        config.active_build_finished_at = now  # type: ignore[attr-defined]
        config.build_status = BuildStatus.ACTIVE  # type: ignore[attr-defined]
        await session.commit()
        return config.id


async def _seed_document(
    *,
    settings: Settings,
    workspace_id: str,
) -> Document:
    """Persist a CSV document and return its metadata row."""

    csv_bytes = (
        b"member_id,email,first_name,last_name\n"
        b"1,alice@example.com,Alice,Anderson\n"
        b"2,bob@example.com,Bob,Brown\n"
    )
    document_id = generate_ulid()
    storage = DocumentStorage(workspace_documents_root(settings, workspace_id))
    stored_uri = storage.make_stored_uri(document_id)
    target_path = storage.path_for(stored_uri)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(csv_bytes)

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            original_filename="members.csv",
            content_type="text/csv",
            byte_size=len(csv_bytes),
            sha256=hashlib.sha256(csv_bytes).hexdigest(),
            stored_uri=stored_uri,
            attributes={},
            expires_at=utc_now() + timedelta(days=30),
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
    return document


async def _seed_workbook_document(
    *,
    settings: Settings,
    workspace_id: str,
) -> Document:
    """Persist a multi-sheet XLSX document and return its metadata row."""

    workbook = openpyxl.Workbook()
    first = workbook.active
    first.title = "Members"
    header = ["member_id", "email", "first_name", "last_name"]
    first.append(header)
    first.append(["101", "first-sheet@example.com", "First", "Sheet"])

    second = workbook.create_sheet("Selected")
    second.append(header)
    second.append(["202", "selected@example.com", "Second", "Worksheet"])

    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    xlsx_bytes = buffer.getvalue()

    document_id = generate_ulid()
    storage = DocumentStorage(workspace_documents_root(settings, workspace_id))
    stored_uri = storage.make_stored_uri(document_id)
    target_path = storage.path_for(stored_uri)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(xlsx_bytes)

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            original_filename="members.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            byte_size=len(xlsx_bytes),
            sha256=hashlib.sha256(xlsx_bytes).hexdigest(),
            stored_uri=stored_uri,
            attributes={},
            expires_at=utc_now() + timedelta(days=30),
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document


async def _auth_headers(client: AsyncClient, *, email: str, password: str) -> dict[str, str]:
    await login(client, email=email, password=password)
    token = client.cookies.get(CSRF_COOKIE)
    assert token, "Missing CSRF cookie"
    return {"X-CSRF-Token": token}


async def _wait_for_completion(
    client: AsyncClient,
    run_id: str,
    *,
    attempts: int = 10,
    delay: float = 0.05,
) -> dict[str, Any]:
    """Poll the run endpoint until it leaves the queued state."""

    payload: dict[str, Any] = {}
    for _ in range(attempts):
        response = await client.get(f"/api/v1/runs/{run_id}")
        payload = response.json()
        if payload.get("status") != "queued":
            return payload
        await asyncio.sleep(delay)
    return payload


async def test_stream_run_safe_mode(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
) -> None:
    """Streaming a run in safe mode should emit events and persist state."""

    settings = override_app_settings(safe_mode=True)
    configuration_id = await _seed_configuration(
        settings=settings,
        workspace_id=seed_identity["workspace_id"],
        tmp_path=tmp_path,
    )
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    events: list[dict[str, Any]] = []
    async with async_client.stream(
        "POST",
        f"/api/v1/configurations/{configuration_id}/runs",
        headers=headers,
        json={"stream": True},
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line:
                continue
            events.append(json.loads(line))

    assert events, "expected streaming events"
    assert events[0]["type"] == "run.queued"
    assert events[-1]["type"] == "run.completed"

    run_id = events[0]["run_id"]
    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "succeeded"
    assert run_payload["exit_code"] == 0
    assert run_payload["build_id"]

    logs_response = await async_client.get(f"/api/v1/runs/{run_id}/logs")
    assert logs_response.status_code == 200
    logs_payload = logs_response.json()
    messages = [entry["message"] for entry in logs_payload["entries"]]
    assert any("safe mode" in message.lower() for message in messages)


async def test_stream_run_respects_persisted_safe_mode_override(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted safe mode state should override environment defaults."""

    settings = override_app_settings(safe_mode=True)
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        service = SafeModeService(session=session, settings=settings)
        await service.update_status(
            enabled=False, detail="Disable safe mode for integration coverage"
        )

    configuration_id = await _seed_configuration(
        settings=settings,
        workspace_id=seed_identity["workspace_id"],
        tmp_path=tmp_path,
    )
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    async def fake_execute_engine(
        self: RunsService,
        *,
        run,
        context,
        options,
        safe_mode_enabled: bool = False,
    ):
        assert not safe_mode_enabled
        completion = await self._complete_run(
            run,
            status=RunStatus.SUCCEEDED,
            exit_code=0,
            summary="Safe mode override respected",
        )
        yield AdeEvent(
            type="run.completed",
            created_at=completion.finished_at or utc_now(),
            run_id=completion.id,
            status=self._status_literal(completion.status),
            execution={"exit_code": completion.exit_code},
            error={"message": completion.error_message} if completion.error_message else None,
        )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    events: list[dict[str, Any]] = []
    async with async_client.stream(
        "POST",
        f"/api/v1/configurations/{configuration_id}/runs",
        headers=headers,
        json={"stream": True},
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line:
                continue
            events.append(json.loads(line))

    assert events, "expected streaming events"
    assert events[-1]["type"] == "run.completed"

    run_id = events[0]["run_id"]
    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "succeeded"
    assert run_payload["exit_code"] == 0
    assert run_payload.get("failure_message") is None
    assert run_payload["build_id"]


async def test_non_stream_run_executes_in_background(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
) -> None:
    """Non-streaming requests should return immediately and finish in the background."""

    settings = override_app_settings(safe_mode=True)
    configuration_id = await _seed_configuration(
        settings=settings,
        workspace_id=seed_identity["workspace_id"],
        tmp_path=tmp_path,
    )
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    response = await async_client.post(
        f"/api/v1/configurations/{configuration_id}/runs",
        headers=headers,
        json={"stream": False},
    )
    assert response.status_code == 201
    payload = response.json()
    run_id = payload["id"]

    completed = await _wait_for_completion(async_client, run_id)
    assert completed["status"] == "succeeded"
    assert completed["exit_code"] == 0


async def test_stream_run_processes_real_documents(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
) -> None:
    """Streaming runs should execute the full engine pipeline against inputs."""

    settings = override_app_settings(safe_mode=False)
    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _seed_real_configuration(
        settings=settings,
        workspace_id=workspace_id,
        tmp_path=tmp_path,
    )
    document = await _seed_document(settings=settings, workspace_id=workspace_id)
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    events: list[dict[str, Any]] = []
    async with async_client.stream(
        "POST",
        f"/api/v1/configurations/{configuration_id}/runs",
        headers=headers,
        json={"stream": True, "options": {"input_document_id": document.id}},
    ) as response:
        assert response.status_code == 200, response.text
        async for line in response.aiter_lines():
            if not line:
                continue
            events.append(json.loads(line))

    assert events and events[0]["type"] == "run.queued"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "succeeded"
    run_id = events[0]["run_id"]

    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "succeeded"
    assert run_payload["exit_code"] == 0
    assert run_payload["build_id"]
    assert run_payload["input"]["document_ids"] == [document.id]
    assert run_payload["input"]["input_sheet_names"] == []

    outputs_response = await async_client.get(f"/api/v1/runs/{run_id}/outputs")
    assert outputs_response.status_code == 200
    outputs_payload = outputs_response.json()
    assert outputs_payload["files"], "expected normalized outputs"
    normalized = next(
        (entry for entry in outputs_payload["files"] if entry["name"].endswith("normalized.xlsx")),
        None,
    )
    assert normalized is not None

    logs_response = await async_client.get(f"/api/v1/runs/{run_id}/logs")
    assert logs_response.status_code == 200
    log_messages = [entry["message"] for entry in logs_response.json()["entries"]]
    assert log_messages, "expected ADE engine logs to be persisted"

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        refreshed = await session.get(Document, document.id)
        assert refreshed is not None
        assert refreshed.last_run_at is not None


async def test_stream_run_honors_input_sheet_override(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
) -> None:
    """Streaming runs should ingest the selected worksheet when provided."""

    settings = override_app_settings(safe_mode=False)
    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _seed_real_configuration(
        settings=settings,
        workspace_id=workspace_id,
        tmp_path=tmp_path,
    )
    document = await _seed_workbook_document(
        settings=settings, workspace_id=workspace_id
    )
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    events: list[dict[str, Any]] = []
    async with async_client.stream(
        "POST",
        f"/api/v1/configurations/{configuration_id}/runs",
        headers=headers,
        json={
            "stream": True,
            "options": {
                "input_document_id": document.id,
                "input_sheet_name": "Selected",
            },
        },
    ) as response:
        assert response.status_code == 200, response.text
        async for line in response.aiter_lines():
            if not line:
                continue
            events.append(json.loads(line))

    assert events and events[0]["type"] == "run.queued"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "succeeded"
    run_id = events[0]["run_id"]

    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "succeeded"
    assert run_payload["exit_code"] == 0
    assert run_payload["build_id"]
    assert run_payload["input"]["document_ids"] == [document.id]
    assert run_payload["input"]["input_sheet_names"] == ["Selected"]

    outputs_response = await async_client.get(f"/api/v1/runs/{run_id}/outputs")
    assert outputs_response.status_code == 200
    outputs_payload = outputs_response.json()
    normalized = next(
        (entry for entry in outputs_payload["files"] if entry["name"].endswith("normalized.xlsx")),
        None,
    )
    assert normalized is not None, "expected normalized workbook output"

    download_response = await async_client.get(normalized["download_url"])
    assert download_response.status_code == 200
    workbook = openpyxl.load_workbook(BytesIO(download_response.content), read_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    rows = list(sheet.iter_rows(values_only=True))
    workbook.close()

    assert rows[0][:4] == ("member_id", "email", "first_name", "last_name")
    data_rows = rows[1:]
    flattened = [
        [str(cell) for cell in row if cell not in (None, "")]
        for row in data_rows
    ]
    assert any("selected@example.com" in row for row in flattened)
    assert all("first-sheet@example.com" not in row for row in flattened)


@pytest.mark.asyncio()
async def test_list_workspace_runs_filters_by_status_and_document(
    session,
    tmp_path: Path,
) -> None:
    service, context, document = await _prepare_service(session, tmp_path)
    configuration = await session.get(Configuration, context.configuration_id)
    assert configuration is not None

    run_success = Run(
        id=generate_ulid(),
        workspace_id=configuration.workspace_id,
        configuration_id=configuration.id,
        configuration_version_id=str(configuration.configuration_version),
        input_document_id=document.id,
        status=RunStatus.SUCCEEDED,
        created_at=utc_now(),
    )
    run_failed = Run(
        id=generate_ulid(),
        workspace_id=configuration.workspace_id,
        configuration_id=configuration.id,
        configuration_version_id=str(configuration.configuration_version),
        status=RunStatus.FAILED,
        created_at=utc_now(),
    )

    session.add_all([run_success, run_failed])
    await session.commit()

    page = await service.list_runs(
        workspace_id=configuration.workspace_id,
        statuses=None,
        input_document_id=None,
        page=1,
        page_size=10,
        include_total=True,
    )

    assert page.total == 3
    assert {run.id for run in page.items} == {
        context.run_id,
        run_success.id,
        run_failed.id,
    }

    filtered = await service.list_runs(
        workspace_id=configuration.workspace_id,
        statuses=[RunStatus.SUCCEEDED],
        input_document_id=document.id,
        page=1,
        page_size=5,
        include_total=True,
    )

    assert filtered.total == 1
    assert [run.id for run in filtered.items] == [run_success.id]


async def test_stream_run_processes_all_worksheets_when_unspecified(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
) -> None:
    """Streaming runs should ingest every worksheet when no override is provided."""

    settings = override_app_settings(safe_mode=False)
    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _seed_real_configuration(
        settings=settings,
        workspace_id=workspace_id,
        tmp_path=tmp_path,
    )
    document = await _seed_workbook_document(
        settings=settings, workspace_id=workspace_id
    )
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    events: list[dict[str, Any]] = []
    async with async_client.stream(
        "POST",
        f"/api/v1/configurations/{configuration_id}/runs",
        headers=headers,
        json={
            "stream": True,
            "options": {
                "input_document_id": document.id,
            },
        },
    ) as response:
        assert response.status_code == 200, response.text
        async for line in response.aiter_lines():
            if not line:
                continue
            events.append(json.loads(line))

    assert events and events[0]["type"] == "run.queued"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "succeeded"
    run_id = events[0]["run_id"]

    outputs_response = await async_client.get(f"/api/v1/runs/{run_id}/outputs")
    assert outputs_response.status_code == 200
    outputs_payload = outputs_response.json()
    normalized = next(
        (entry for entry in outputs_payload["files"] if entry["name"].endswith("normalized.xlsx")),
        None,
    )
    assert normalized is not None, "expected normalized workbook output"

    download_response = await async_client.get(normalized["download_url"])
    assert download_response.status_code == 200
    workbook = openpyxl.load_workbook(BytesIO(download_response.content), read_only=True)
    rows = [list(sheet.iter_rows(values_only=True)) for sheet in workbook]
    workbook.close()

    flattened = [cell for sheet_rows in rows for row in sheet_rows for cell in row if cell]
    assert "first-sheet@example.com" in flattened
    assert "selected@example.com" in flattened


async def test_stream_run_limits_to_requested_sheet_list(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
) -> None:
    """Streaming runs should narrow ingestion to the requested worksheet list."""

    settings = override_app_settings(safe_mode=False)
    workspace_id = seed_identity["workspace_id"]
    configuration_id = await _seed_real_configuration(
        settings=settings,
        workspace_id=workspace_id,
        tmp_path=tmp_path,
    )
    document = await _seed_workbook_document(
        settings=settings, workspace_id=workspace_id
    )
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    events: list[dict[str, Any]] = []
    async with async_client.stream(
        "POST",
        f"/api/v1/configurations/{configuration_id}/runs",
        headers=headers,
        json={
            "stream": True,
            "options": {
                "input_document_id": document.id,
                "input_sheet_names": ["Selected"],
            },
        },
    ) as response:
        assert response.status_code == 200, response.text
        async for line in response.aiter_lines():
            if not line:
                continue
            events.append(json.loads(line))

    assert events and events[0]["type"] == "run.queued"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "succeeded"
    run_id = events[0]["run_id"]

    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["input"]["input_sheet_names"] == ["Selected"]
    assert run_payload["build_id"]

    outputs_response = await async_client.get(f"/api/v1/runs/{run_id}/outputs")
    assert outputs_response.status_code == 200
    outputs_payload = outputs_response.json()
    normalized = next(
        (entry for entry in outputs_payload["files"] if entry["name"].endswith("normalized.xlsx")),
        None,
    )
    assert normalized is not None, "expected normalized workbook output"

    download_response = await async_client.get(normalized["download_url"])
    assert download_response.status_code == 200
    workbook = openpyxl.load_workbook(BytesIO(download_response.content), read_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    rows = list(sheet.iter_rows(values_only=True))
    workbook.close()

    assert rows[0][:4] == ("member_id", "email", "first_name", "last_name")
    data_rows = rows[1:]
    flattened = [
        [str(cell) for cell in row if cell not in (None, "")]
        for row in data_rows
    ]
    assert any("selected@example.com" in row for row in flattened)
    assert all("first-sheet@example.com" not in row for row in flattened)
