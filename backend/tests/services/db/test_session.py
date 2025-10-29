"""Tests covering the asynchronous session dependency wiring."""

from __future__ import annotations

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
            now_iso = datetime.now(UTC).isoformat()
            payload = {
                "config_id": config_id,
                "workspace_id": workspace_id,
                "title": "Session Config",
                "note": None,
                "status": "inactive",
                "version": "v1",
                "files_hash": "",
                "package_sha256": None,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await session.execute(
                text(
                    """
                    INSERT INTO configs (
                        config_id,
                        workspace_id,
                        title,
                        note,
                        status,
                        version,
                        files_hash,
                        package_sha256,
                        created_at,
                        updated_at,
                        created_by,
                        activated_at,
                        activated_by,
                        archived_at,
                        archived_by
                    ) VALUES (
                        :config_id,
                        :workspace_id,
                        :title,
                        :note,
                        :status,
                        :version,
                        :files_hash,
                        :package_sha256,
                        :created_at,
                        :updated_at,
                        NULL,
                        NULL,
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
