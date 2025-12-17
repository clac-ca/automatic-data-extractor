"""Integration tests for the builds API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.encoding import json_dumps
from ade_api.db.mixins import generate_uuid7
from ade_api.features.builds import service as builds_service_module
from ade_api.features.builds.builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    BuildStep,
)
from ade_api.infra.storage import workspace_config_root
from ade_api.models import Configuration, ConfigurationStatus
from ade_api.settings import Settings
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
        json_dumps({
            "build_id": build_id,
            "workspace_id": workspace_id,
            "configuration_id": configuration_id,
        })
        venv_root.mkdir(parents=True, exist_ok=True)
        for event in self._events:
            yield event


@pytest.fixture(autouse=True)
def _override_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the builds service uses the stub builder in integration tests."""

    monkeypatch.setattr(builds_service_module, "VirtualEnvironmentBuilder", StubBuilder)
    StubBuilder.events = []


async def _seed_configuration(
    *,
    session: AsyncSession,
    settings: Settings,
    workspace_id: UUID,
) -> UUID:
    """Insert a configuration row and ensure on-disk config artifacts exist."""

    configuration_id = generate_uuid7()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace_id,
        display_name="Test Configuration",
        status=ConfigurationStatus.ACTIVE,
        content_digest="test-digest",
    )
    session.add(configuration)
    await session.commit()

    config_root = workspace_config_root(settings, workspace_id, configuration_id)
    (config_root / "src" / "ade_config").mkdir(parents=True, exist_ok=True)
    (config_root / "pyproject.toml").write_text(
        """
[project]
name = "ade-config"
version = "1.6.1"
""".strip(),
        encoding="utf-8",
    )
    (config_root / "src" / "ade_config" / "manifest.toml").write_text(
        """
schema = "ade.manifest/v1"
version = "1.0.0"
script_api_version = 3
columns = []

[writer]
append_unmapped_columns = true
unmapped_prefix = "raw_"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return configuration_id


async def _auth_headers(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, str]:
    token, _ = await login(client, email=email, password=password)
    return {"Authorization": f"Bearer {token}"}


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
        if payload.get("status") not in ("queued", "building"):
            return payload
        await asyncio.sleep(delay)
    return payload


async def test_background_build_executes_to_completion(
    async_client: AsyncClient,
    seed_identity,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Non-streaming build requests should run in a background task and finish."""

    configuration_id = await _seed_configuration(
        session=session,
        settings=settings,
        workspace_id=seed_identity.workspace_id,
    )

    StubBuilder.events = [
        BuilderStepEvent(step=BuildStep.CREATE_VENV, message="create venv"),
        BuilderLogEvent(message="background log"),
        BuilderArtifactsEvent(
            artifacts=BuildArtifacts(python_version="3.11.0", engine_version="1.2.3")
        ),
    ]

    owner = seed_identity.workspace_owner
    headers = await _auth_headers(
        async_client,
        email=owner.email,
        password=owner.password,
    )

    workspace_id = seed_identity.workspace_id
    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
        json={},
    )
    assert response.status_code == 201
    build_id = response.json()["id"]

    completed = await _wait_for_build_completion(
        async_client,
        build_id,
        headers=headers,
    )
    assert completed["status"] == "ready"
    assert completed["exit_code"] == 0


async def test_list_builds_with_filters_and_limits(
    async_client: AsyncClient,
    seed_identity,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Configuration-scoped build listing should support filters and pagination."""

    configuration_id = await _seed_configuration(
        session=session,
        settings=settings,
        workspace_id=seed_identity.workspace_id,
    )

    owner = seed_identity.workspace_owner
    headers = await _auth_headers(
        async_client,
        email=owner.email,
        password=owner.password,
    )
    workspace_id = seed_identity.workspace_id

    StubBuilder.events = [
        BuilderStepEvent(step=BuildStep.CREATE_VENV, message="create venv"),
        BuilderArtifactsEvent(
            artifacts=BuildArtifacts(python_version="3.11.0", engine_version="1.2.3")
        ),
    ]
    first_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
        json={},
    )
    assert first_response.status_code == 201
    active_build_id = first_response.json()["id"]
    active_build = await _wait_for_build_completion(
        async_client,
        active_build_id,
        headers=headers,
    )
    assert active_build["status"] == "ready"

    StubBuilder.events = [
        BuilderLogEvent(message="expected failure"),
    ]
    second_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
        json={"options": {"force": True}},
    )
    assert second_response.status_code == 201
    failed_build_id = second_response.json()["id"]
    failed_build = await _wait_for_build_completion(
        async_client,
        failed_build_id,
        headers=headers,
    )
    assert failed_build["status"] == "failed"

    failed_only = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
        params={"status": ["failed"], "limit": 1},
    )
    assert failed_only.status_code == 200
    failed_payload = failed_only.json()
    assert failed_payload["page_size"] == 1
    assert [item["id"] for item in failed_payload["items"]] == [failed_build_id]
    assert "total" not in failed_payload

    all_builds = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
    )
    assert all_builds.status_code == 200
    build_ids = [item["id"] for item in all_builds.json()["items"]]
    assert build_ids == [failed_build_id, active_build_id]
