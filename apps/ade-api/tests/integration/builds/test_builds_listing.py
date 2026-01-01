import json
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


async def test_list_builds_with_filters_and_limits(
    async_client: AsyncClient,
    seed_identity,
    session,
    settings: Settings,
) -> None:
    """Configuration-scoped build listing should support filters and pagination."""

    configuration_id = await seed_configuration(
        session=session,
        settings=settings,
        workspace_id=seed_identity.workspace_id,
    )

    owner = seed_identity.workspace_owner
    headers = await auth_headers(
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
    active_build = await wait_for_build_completion(
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
    failed_build = await wait_for_build_completion(
        async_client,
        failed_build_id,
        headers=headers,
    )
    assert failed_build["status"] == "failed"
    assert active_build_id == failed_build_id

    failed_filters = json.dumps([{"id": "status", "operator": "eq", "value": "failed"}])
    failed_only = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
        params={"filters": failed_filters, "perPage": 1},
    )
    assert failed_only.status_code == 200
    failed_payload = failed_only.json()
    assert failed_payload["perPage"] == 1
    assert failed_payload["pageCount"] == 1
    assert failed_payload["total"] == 1
    assert [item["id"] for item in failed_payload["items"]] == [failed_build_id]

    all_builds = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
        headers=headers,
    )
    assert all_builds.status_code == 200
    all_payload = all_builds.json()
    build_ids = [item["id"] for item in all_payload["items"]]
    assert all_payload["total"] == 1
    assert build_ids == [failed_build_id]
