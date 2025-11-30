"""Integration tests for the builds API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from ade_api.features.builds import service as builds_service_module
from ade_api.features.builds.builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    BuildStep,
)
from ade_api.features.configs.models import Configuration, ConfigurationStatus
from ade_api.settings import Settings
from ade_api.shared.db.mixins import generate_ulid
from ade_api.shared.db.session import get_sessionmaker
from tests.utils import login

pytestmark = pytest.mark.asyncio


class StubBuilder:
    """Test double that yields a predetermined stream of build events."""

    events: list[BuilderEvent] = []

    def __init__(self) -> None:
        self._events = [*type(self).events]

    async def build_stream(
        self,
        *,
        build_id: str,
        workspace_id: str,
        configuration_id: str,
        venv_root: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
        fingerprint: str | None = None,
    ) -> AsyncIterator[BuilderEvent]:
        venv_root.mkdir(parents=True, exist_ok=True)
        for event in self._events:
            yield event


@pytest.fixture(autouse=True)
def _override_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the builds service uses the stub builder in integration tests."""

    monkeypatch.setattr(builds_service_module, "VirtualEnvironmentBuilder", StubBuilder)
    StubBuilder.events = []


async def _seed_configuration(*, settings: Settings, workspace_id: str) -> str:
    """Insert a configuration row and ensure on-disk config artifacts exist."""

    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        configuration_id = generate_ulid()
        configuration = Configuration(
            id=configuration_id,
            workspace_id=workspace_id,
            display_name="Test Configuration",
            status=ConfigurationStatus.ACTIVE,
            content_digest="test-digest",
        )
        session.add(configuration)
        await session.commit()

    config_root = settings.configs_dir / workspace_id / "config_packages" / configuration_id
    (config_root / "src" / "ade_config").mkdir(parents=True, exist_ok=True)
    (config_root / "pyproject.toml").write_text(
        """
[project]
name = "ade-config"
version = "0.2.0"
""".strip(),
        encoding="utf-8",
    )
    (config_root / "src" / "ade_config" / "manifest.json").write_text("{}", encoding="utf-8")
    return configuration_id


async def _auth_headers(
    client: AsyncClient,
    *,
    email: str,
    password: str,
    settings: Settings,
) -> dict[str, str]:
    await login(client, email=email, password=password)
    csrf_cookie = client.cookies.get(settings.session_csrf_cookie_name)
    assert csrf_cookie, "CSRF cookie missing after login"
    return {"X-CSRF-Token": csrf_cookie}


async def test_stream_build_emits_events_and_logs(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
) -> None:
    """Streaming build requests should emit NDJSON events and persist build state."""

    settings = override_app_settings()
    configuration_id = await _seed_configuration(
        settings=settings,
        workspace_id=seed_identity["workspace_id"],
    )

    StubBuilder.events = [
        BuilderStepEvent(step=BuildStep.CREATE_VENV, message="create venv"),
        BuilderLogEvent(message="install log"),
        BuilderStepEvent(step=BuildStep.INSTALL_ENGINE, message="install engine"),
        BuilderArtifactsEvent(
            artifacts=BuildArtifacts(python_version="3.11.8", engine_version="1.2.3")
        ),
    ]

    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client,
        email=owner["email"],
        password=owner["password"],  # type: ignore[index]
        settings=settings,
    )

    workspace_id = seed_identity["workspace_id"]
    events: list[dict[str, Any]] = []
    async with async_client.stream(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
        json={"stream": True},
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                events.append(json.loads(line.removeprefix("data: ")))

    assert events, "expected streaming events"
    assert events[0]["type"] == "build.created"
    assert events[-1]["type"] == "build.completed"

    build_id = events[0]["build_id"]

    detail = await async_client.get(f"/api/v1/builds/{build_id}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "active"
    assert payload["exit_code"] == 0
    assert payload["summary"] == "Build succeeded"


async def _wait_for_build_completion(
    client: AsyncClient,
    build_id: str,
    *,
    attempts: int = 20,
    delay: float = 0.05,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for _ in range(attempts):
        response = await client.get(f"/api/v1/builds/{build_id}", headers=headers)
        payload = response.json()
        if payload.get("status") != "queued":
            return payload
        await asyncio.sleep(delay)
    return payload


async def test_background_build_executes_to_completion(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    override_app_settings,
) -> None:
    """Non-streaming build requests should run in a background task and finish."""

    settings = override_app_settings()
    configuration_id = await _seed_configuration(
        settings=settings,
        workspace_id=seed_identity["workspace_id"],
    )

    StubBuilder.events = [
        BuilderStepEvent(step=BuildStep.CREATE_VENV, message="create venv"),
        BuilderLogEvent(message="background log"),
        BuilderArtifactsEvent(
            artifacts=BuildArtifacts(python_version="3.11.8", engine_version="1.2.3")
        ),
    ]

    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client,
        email=owner["email"],
        password=owner["password"],  # type: ignore[index]
        settings=settings,
    )

    workspace_id = seed_identity["workspace_id"]
    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
        json={"stream": False},
    )
    assert response.status_code == 201
    build_id = response.json()["id"]

    completed = await _wait_for_build_completion(
        async_client,
        build_id,
        headers=headers,
    )
    assert completed["status"] == "active"
    assert completed["exit_code"] == 0
