"""Integration coverage for the runs API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from io import BytesIO
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
import openpyxl

from ade_api.features.builds.models import ConfigurationBuild, ConfigurationBuildStatus
from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.features.documents.models import Document
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.runs.models import RunStatus
from ade_api.features.runs.schemas import RunCompletedEvent
from ade_api.features.runs.service import RunsService
from ade_api.features.system_settings.service import SafeModeService
from ade_api.settings import Settings, get_settings
from ade_api.shared.core.time import utc_now
from ade_api.shared.db.mixins import generate_ulid
from ade_api.shared.db.session import get_sessionmaker
from tests.utils import login

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


async def _seed_configuration(
    *,
    settings: Settings,
    workspace_id: str,
    tmp_path: Path,
) -> str:
    """Insert a configuration and active build used to drive runs tests."""

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        config = Configuration(
            workspace_id=workspace_id,
            config_id=generate_ulid(),
            display_name="Test Configuration",
            status=ConfigurationStatus.ACTIVE,
        )
        session.add(config)
        await session.flush()

        venv_path = tmp_path / f"venv-{config.config_id}"
        venv_path.mkdir(parents=True, exist_ok=True)

        build = ConfigurationBuild(
            workspace_id=workspace_id,
            config_id=config.config_id,
            configuration_id=config.id,
            build_id=generate_ulid(),
            status=ConfigurationBuildStatus.ACTIVE,
            venv_path=str(venv_path),
        )
        session.add(build)
        await session.commit()
        return config.config_id


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
        config = Configuration(
            workspace_id=workspace_id,
            config_id=generate_ulid(),
            display_name="Real Config",
            status=ConfigurationStatus.ACTIVE,
            config_version=1,
            content_digest="integration-test",
        )
        session.add(config)
        await session.flush()

        venv_root = Path(settings.venvs_dir)
        venv_path = venv_root / workspace_id / config.config_id / "integration"
        if venv_path.exists():
            shutil.rmtree(venv_path)
        venv_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

        pip_exe = _venv_executable(venv_path, "pip")
        _pip_install(pip_exe, _ENGINE_PACKAGE)
        config_src = tmp_path / f"ade-config-{config.config_id}"
        shutil.copytree(_CONFIG_TEMPLATE, config_src, dirs_exist_ok=True)
        _pip_install(pip_exe, config_src)

        python_exe = _venv_executable(venv_path, "python")
        now = utc_now()
        build = ConfigurationBuild(
            workspace_id=workspace_id,
            config_id=config.config_id,
            configuration_id=config.id,
            build_id=generate_ulid(),
            status=ConfigurationBuildStatus.ACTIVE,
            venv_path=str(venv_path),
            config_version=config.config_version,
            content_digest=config.content_digest,
            engine_version="0.1.0",
            engine_spec=settings.engine_spec,
            python_version=sys.version.split()[0],
            python_interpreter=str(python_exe),
            started_at=now,
            built_at=now,
        )
        session.add(build)
        await session.commit()
        return config.config_id


async def _seed_document(
    *,
    settings: Settings,
    workspace_id: str,
) -> Document:
    """Persist a CSV document and return its metadata row."""

    csv_bytes = (
        "member_id,email,first_name,last_name\n"
        "1,alice@example.com,Alice,Anderson\n"
        "2,bob@example.com,Bob,Brown\n"
    ).encode("utf-8")
    document_id = generate_ulid()
    storage = DocumentStorage(Path(settings.documents_dir))
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
    storage = DocumentStorage(Path(settings.documents_dir))
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
    config_id = await _seed_configuration(
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
        f"/api/v1/configs/{config_id}/runs",
        headers=headers,
        json={"stream": True},
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line:
                continue
            events.append(json.loads(line))

    assert events, "expected streaming events"
    assert events[0]["type"] == "run.created"
    assert events[-1]["type"] == "run.completed"

    run_id = events[0]["run_id"]
    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "succeeded"
    assert run_payload["exit_code"] == 0

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

    config_id = await _seed_configuration(
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
        yield RunCompletedEvent(
            run_id=completion.id,
            created=self._epoch_seconds(completion.finished_at),
            status=self._status_literal(completion.status),
            exit_code=completion.exit_code,
            error_message=completion.error_message,
        )

    monkeypatch.setattr(RunsService, "_execute_engine", fake_execute_engine)

    events: list[dict[str, Any]] = []
    async with async_client.stream(
        "POST",
        f"/api/v1/configs/{config_id}/runs",
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
    assert run_payload.get("summary") == "Safe mode override respected"


async def test_non_stream_run_executes_in_background(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
) -> None:
    """Non-streaming requests should return immediately and finish in the background."""

    settings = override_app_settings(safe_mode=True)
    config_id = await _seed_configuration(
        settings=settings,
        workspace_id=seed_identity["workspace_id"],
        tmp_path=tmp_path,
    )
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    response = await async_client.post(
        f"/api/v1/configs/{config_id}/runs",
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
    config_id = await _seed_real_configuration(
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
        f"/api/v1/configs/{config_id}/runs",
        headers=headers,
        json={"stream": True, "options": {"input_document_id": document.id}},
    ) as response:
        assert response.status_code == 200, response.text
        async for line in response.aiter_lines():
            if not line:
                continue
            events.append(json.loads(line))

    assert events and events[0]["type"] == "run.created"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "succeeded"
    run_id = events[0]["run_id"]

    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "succeeded"
    assert run_payload["exit_code"] == 0
    assert run_payload["input_document_id"] == document.id
    assert run_payload["input_sheet_name"] is None
    assert run_payload["input_sheet_names"] is None

    outputs_response = await async_client.get(f"/api/v1/runs/{run_id}/outputs")
    assert outputs_response.status_code == 200
    outputs_payload = outputs_response.json()
    assert outputs_payload["files"], "expected normalized outputs"
    assert any(
        entry["path"].endswith("normalized.xlsx") for entry in outputs_payload["files"]
    )

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
    config_id = await _seed_real_configuration(
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
        f"/api/v1/configs/{config_id}/runs",
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

    assert events and events[0]["type"] == "run.created"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "succeeded"
    run_id = events[0]["run_id"]

    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "succeeded"
    assert run_payload["exit_code"] == 0
    assert run_payload["input_document_id"] == document.id
    assert run_payload["input_sheet_name"] == "Selected"
    assert run_payload["input_sheet_names"] == ["Selected"]

    outputs_response = await async_client.get(f"/api/v1/runs/{run_id}/outputs")
    assert outputs_response.status_code == 200
    outputs_payload = outputs_response.json()
    normalized = next(
        (entry for entry in outputs_payload["files"] if entry["path"].endswith("normalized.xlsx")),
        None,
    )
    assert normalized is not None, "expected normalized workbook output"

    download_response = await async_client.get(
        f"/api/v1/runs/{run_id}/outputs/{normalized['path']}"
    )
    assert download_response.status_code == 200
    workbook = openpyxl.load_workbook(BytesIO(download_response.content), read_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    rows = list(sheet.iter_rows(values_only=True))
    workbook.close()

    assert rows[0][:4] == ("Member ID", "Email", "First Name", "Last Name")
    data_rows = rows[1:]
    flattened = [
        [str(cell) for cell in row if cell not in (None, "")]
        for row in data_rows
    ]
    assert any("selected@example.com" in row for row in flattened)
    assert all("first-sheet@example.com" not in row for row in flattened)


async def test_stream_run_processes_all_worksheets_when_unspecified(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
    tmp_path,
) -> None:
    """Streaming runs should ingest every worksheet when no override is provided."""

    settings = override_app_settings(safe_mode=False)
    workspace_id = seed_identity["workspace_id"]
    config_id = await _seed_real_configuration(
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
        f"/api/v1/configs/{config_id}/runs",
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

    assert events and events[0]["type"] == "run.created"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "succeeded"
    run_id = events[0]["run_id"]

    outputs_response = await async_client.get(f"/api/v1/runs/{run_id}/outputs")
    assert outputs_response.status_code == 200
    outputs_payload = outputs_response.json()
    normalized = next(
        (entry for entry in outputs_payload["files"] if entry["path"].endswith("normalized.xlsx")),
        None,
    )
    assert normalized is not None, "expected normalized workbook output"

    download_response = await async_client.get(
        f"/api/v1/runs/{run_id}/outputs/{normalized['path']}"
    )
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
    config_id = await _seed_real_configuration(
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
        f"/api/v1/configs/{config_id}/runs",
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

    assert events and events[0]["type"] == "run.created"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["status"] == "succeeded"
    run_id = events[0]["run_id"]

    run_response = await async_client.get(f"/api/v1/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["input_sheet_name"] == "Selected"
    assert run_payload["input_sheet_names"] == ["Selected"]

    outputs_response = await async_client.get(f"/api/v1/runs/{run_id}/outputs")
    assert outputs_response.status_code == 200
    outputs_payload = outputs_response.json()
    normalized = next(
        (entry for entry in outputs_payload["files"] if entry["path"].endswith("normalized.xlsx")),
        None,
    )
    assert normalized is not None, "expected normalized workbook output"

    download_response = await async_client.get(
        f"/api/v1/runs/{run_id}/outputs/{normalized['path']}"
    )
    assert download_response.status_code == 200
    workbook = openpyxl.load_workbook(BytesIO(download_response.content), read_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    rows = list(sheet.iter_rows(values_only=True))
    workbook.close()

    assert rows[0][:4] == ("Member ID", "Email", "First Name", "Last Name")
    data_rows = rows[1:]
    flattened = [
        [str(cell) for cell in row if cell not in (None, "")]
        for row in data_rows
    ]
    assert any("selected@example.com" in row for row in flattened)
    assert all("first-sheet@example.com" not in row for row in flattened)
