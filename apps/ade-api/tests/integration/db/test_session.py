"""Tests covering the session dependency wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from ade_api.db import get_db


@pytest.mark.asyncio
async def test_session_dependency_commits_and_populates_context(
    db_connection,
    settings,
    seed_identity,
):
    """The session dependency should commit writes."""

    route_path = "/__tests__/configurations"
    workspace_id = seed_identity.workspace_id
    workspace_id_str = str(workspace_id)

    from ade_api.main import create_app
    from ade_api.settings import get_settings

    app = create_app(settings=settings)

    app.dependency_overrides[get_settings] = lambda: app.state.settings

    @app.post(route_path)
    def _create_config(
        session: Annotated[Session, Depends(get_db)],
    ) -> dict[str, bool | str]:
        assert isinstance(session, Session)

        configuration_id = str(uuid4())
        now_iso = datetime.now(UTC).isoformat()
        payload = {
            "id": configuration_id,
            "workspace_id": workspace_id_str,
            "display_name": "Session Configuration",
            "status": "draft",
            "content_digest": None,
            "activated_at": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        session.execute(
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(route_path)
        response.raise_for_status()
        data = response.json()

    configuration_id = data["configuration_id"]
    assert data["session_attached"] is True

    result = db_connection.execute(
        text("SELECT COUNT(1) FROM configurations WHERE id = :configuration_id"),
        {"configuration_id": configuration_id},
    )
    assert result.scalar_one() == 1
