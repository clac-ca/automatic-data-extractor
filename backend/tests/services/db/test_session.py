"""Tests covering the asynchronous session dependency wiring."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.db.engine import get_engine
from backend.app.shared.db.mixins import generate_ulid
from backend.app.shared.db.session import get_session


@pytest.mark.asyncio
async def test_session_dependency_commits_and_populates_context(
    app,
    async_client,
    seed_identity,
):
    """The session dependency should attach to the request and commit writes."""

    route_path = "/__tests__/configs"
    workspace_id = seed_identity["workspace_id"]

    if not any(route.path == route_path for route in app.router.routes):

        @app.post(route_path)
        async def _create_config(
            request: Request,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> dict[str, bool | str]:
            assert isinstance(session, AsyncSession)
            assert request.state.db_session is session

            config_id = generate_ulid()
            config_version_id = generate_ulid()
            payload = {
                "config_id": config_id,
                "config_version_id": config_version_id,
                "manifest_json": json.dumps({"files_hash": ""}),
                "files_hash": "",
                "slug": "session-check",
                "title": "Session Config",
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "workspace_id": workspace_id,
            }
            await session.execute(
                text(
                    """
                    INSERT INTO configs (
                        config_id,
                        workspace_id,
                        slug,
                        title,
                        created_at,
                        updated_at,
                        created_by
                    ) VALUES (
                        :config_id,
                        :workspace_id,
                        :slug,
                        :title,
                        :created_at,
                        :updated_at,
                        NULL
                    )
                    """
                ),
                payload,
            )
            await session.execute(
                text(
                    """
                    INSERT INTO config_versions (
                        config_version_id,
                        config_id,
                        semver,
                        status,
                        message,
                        manifest_json,
                        files_hash,
                        created_at,
                        updated_at,
                        created_by,
                        published_at
                    ) VALUES (
                        :config_version_id,
                        :config_id,
                        'draft',
                        'draft',
                        NULL,
                        :manifest_json,
                        :files_hash,
                        :created_at,
                        :updated_at,
                        NULL,
                        NULL
                    )
                    """
                ),
                payload,
            )
            return {"session_attached": True, "config_id": config_id}

    response = await async_client.post(route_path)
    response.raise_for_status()
    data = response.json()
    config_id = data["config_id"]
    assert data["session_attached"] is True

    engine = get_engine()
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT COUNT(1) FROM configs WHERE config_id = :config_id"
            ),
            {"config_id": config_id},
        )
        assert result.scalar_one() == 1
