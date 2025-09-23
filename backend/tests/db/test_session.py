"""Tests covering the asynchronous session dependency wiring."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.service import ServiceContext, get_service_context
from backend.app.db.engine import get_engine
from backend.app.db.mixins import generate_ulid
from backend.app.db.session import get_session


@pytest.mark.asyncio
async def test_session_dependency_commits_and_populates_context(
    app,
    async_client,
):
    """The session dependency should attach to the request and commit writes."""

    route_path = "/__tests__/configurations"

    if not any(route.path == route_path for route in app.router.routes):

        @app.post(route_path, dependencies=[Depends(get_session)])
        async def _create_configuration(
            request: Request,
            context: ServiceContext = Depends(get_service_context),
        ) -> dict[str, bool | str]:
            assert isinstance(context.session, AsyncSession)
            assert request.state.db_session is context.session

            configuration_id = generate_ulid()
            payload = {
                "configuration_id": configuration_id,
                "document_type": "invoice",
                "title": "Test Configuration",
                "version": 1,
                "is_active": False,
                "payload": json.dumps({}),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await context.session.execute(
                text(
                    """
                    INSERT INTO configurations (
                        configuration_id,
                        document_type,
                        title,
                        version,
                        is_active,
                        payload,
                        created_at,
                        updated_at
                    ) VALUES (
                        :configuration_id,
                        :document_type,
                        :title,
                        :version,
                        :is_active,
                        :payload,
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
            text(
                "SELECT COUNT(1) FROM configurations WHERE configuration_id = :configuration_id"
            ),
            {"configuration_id": configuration_id},
        )
        assert result.scalar_one() == 1
