from uuid import uuid4

import pytest
from httpx import AsyncClient

from ade_api.settings import Settings
from tests.integration.builds.helpers import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderLogEvent,
    BuilderStepEvent,
    BuildStep,
    StubBuilder,
    auth_headers,
    seed_configuration,
    wait_for_build_completion,
)

pytestmark = pytest.mark.asyncio


async def test_background_build_executes_to_completion(
    async_client: AsyncClient,
    seed_identity,
    session,
    settings: Settings,
) -> None:
    """Non-streaming build requests should run in a background task and finish."""

    configuration_id = await seed_configuration(
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
    headers = await auth_headers(
        async_client,
        email=owner.email,
        password=owner.password,
    )

    workspace_id = seed_identity.workspace_id
    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers={**headers, "Idempotency-Key": f"idem-{uuid4().hex}"},
        json={},
    )
    assert response.status_code == 201
    build_id = response.json()["id"]

    completed = await wait_for_build_completion(
        async_client,
        build_id,
        headers=headers,
    )
    assert completed["status"] == "ready"
    assert completed["exit_code"] == 0
