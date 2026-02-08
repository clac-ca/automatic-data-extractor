"""Shared helpers for configuration integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from httpx import AsyncClient

from ade_api.settings import Settings
from tests.api.utils import login


async def auth_headers(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, str]:
    token, _ = await login(client, email=email, password=password)
    return {"X-API-Key": token}


async def create_from_template(
    client: AsyncClient,
    *,
    workspace_id: str,
    headers: dict[str, str],
    display_name: str = "Config A",
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
        json={
            "display_name": display_name,
            "source": {"type": "template"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def config_path(
    settings: Settings,
    workspace_id: UUID | str,
    configuration_id: UUID | str,
) -> Path:
    return (
        Path(settings.configs_dir)
        / str(workspace_id)
        / "config_packages"
        / str(configuration_id)
    )
