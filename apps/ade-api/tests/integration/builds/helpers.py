from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.encoding import json_dumps
from ade_api.db.mixins import generate_uuid7
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

__all__ = [
    "BuildArtifacts",
    "BuilderArtifactsEvent",
    "BuilderEvent",
    "BuilderLogEvent",
    "BuilderStepEvent",
    "BuildStep",
    "StubBuilder",
    "auth_headers",
    "seed_configuration",
    "wait_for_build_completion",
]


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


async def seed_configuration(
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


async def auth_headers(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, str]:
    token, _ = await login(client, email=email, password=password)
    return {"Authorization": f"Bearer {token}"}


async def wait_for_build_completion(
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
