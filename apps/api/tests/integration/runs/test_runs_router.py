"""Integration coverage for the runs API."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from apps.api.app.features.builds.models import ConfigurationBuild, ConfigurationBuildStatus
from apps.api.app.features.configs.models import Configuration, ConfigurationStatus
from apps.api.app.settings import Settings, get_settings
from apps.api.app.shared.db.mixins import generate_ulid
from apps.api.app.shared.db.session import get_sessionmaker
from apps.api.tests.utils import login

pytestmark = pytest.mark.asyncio

_SETTINGS = get_settings()
CSRF_COOKIE = _SETTINGS.session_csrf_cookie_name


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
