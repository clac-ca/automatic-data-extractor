"""Tests covering the asynchronous session dependency wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.shared.db.engine import get_engine
from ade_api.shared.db.mixins import generate_ulid
from ade_api.shared.db.session import get_session


@pytest.mark.asyncio
async def test_session_dependency_commits_and_populates_context(
    app,
    async_client,
    seed_identity,
):
    """The session dependency should attach to the request and commit writes."""

    route_path = "/__tests__/configurations"
    workspace_id = seed_identity["workspace_id"]

    if not any(route.path == route_path for route in app.router.routes):

        @app.post(route_path)
        async def _create_config(
            request: Request,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> dict[str, bool | str]:
            assert isinstance(session, AsyncSession)
            assert request.state.db_session is session

            configuration_id = generate_ulid()
            now_iso = datetime.now(UTC).isoformat()
            payload = {
                "id": configuration_id,
                "workspace_id": workspace_id,
                "display_name": "Session Configuration",
                "status": "draft",
                "content_digest": None,
                "activated_at": None,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await session.execute(
                text(
                    """
                    INSERT INTO configurations (
                        id,
                        workspace_id,
                        display_name,
                        status,
                        content_digest,
                        activated_at,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :workspace_id,
                        :display_name,
                        :status,
                        :content_digest,
                        :activated_at,
                        :created_at,
                        :updated_at
                    )
                    """
                ),
                payload,
            )
            return {"session_attached": True, "configuration_id": configuration_id}

    response = await async_client.post(route_path)
    response.raise_for_status()
    data = response.json()
    configuration_id = data["configuration_id"]
    assert data["session_attached"] is True

    engine = get_engine()
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT COUNT(1) FROM configurations WHERE id = :configuration_id"),
            {"configuration_id": configuration_id},
        )
        assert result.scalar_one() == 1
