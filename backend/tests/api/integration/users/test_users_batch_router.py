"""Integration tests for Graph-style user batch endpoint."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.api.utils import login

pytestmark = pytest.mark.asyncio


def _password_profile() -> dict[str, object]:
    return {
        "mode": "explicit",
        "password": "notsecret1!Ab",
        "forceChangeOnNextSignIn": False,
    }


async def test_batch_user_mutations_support_partial_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    orphan = seed_identity.orphan
    member = seed_identity.member
    missing_user = uuid4()
    created_email = f"batched-{uuid4().hex[:8]}@example.com"

    response = await async_client.post(
        "/api/v1/$batch",
        headers={"X-API-Key": token},
        json={
            "requests": [
                {
                    "id": "create-1",
                    "method": "POST",
                    "url": "/users",
                    "body": {
                        "email": created_email,
                        "displayName": "Batch Created",
                        "passwordProfile": _password_profile(),
                    },
                },
                {
                    "id": "update-1",
                    "method": "PATCH",
                    "url": f"/users/{orphan.id}",
                    "body": {"department": "Data Ops"},
                },
                {
                    "id": "deactivate-1",
                    "method": "POST",
                    "url": f"/users/{member.id}/deactivate",
                },
                {
                    "id": "missing-1",
                    "method": "PATCH",
                    "url": f"/users/{missing_user}",
                    "body": {"department": "Ghost"},
                },
            ]
        },
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    statuses = {item["id"]: item["status"] for item in payload["responses"]}
    assert statuses == {
        "create-1": 201,
        "update-1": 200,
        "deactivate-1": 200,
        "missing-1": 404,
    }

    created = next(item for item in payload["responses"] if item["id"] == "create-1")
    created_user_id = created["body"]["user"]["id"]
    assert created["headers"]["Location"] == f"/api/v1/users/{created_user_id}"

    created_get = await async_client.get(
        f"/api/v1/users/{created_user_id}",
        headers={"X-API-Key": token},
    )
    assert created_get.status_code == 200, created_get.text
    assert created_get.json()["email"] == created_email

    orphan_get = await async_client.get(
        f"/api/v1/users/{orphan.id}",
        headers={"X-API-Key": token},
    )
    assert orphan_get.status_code == 200, orphan_get.text
    assert orphan_get.json()["department"] == "Data Ops"

    member_get = await async_client.get(
        f"/api/v1/users/{member.id}",
        headers={"X-API-Key": token},
    )
    assert member_get.status_code == 200, member_get.text
    assert member_get.json()["is_active"] is False


async def test_batch_dependency_failure_returns_424_and_skips_dependent_item(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    orphan = seed_identity.orphan
    response = await async_client.post(
        "/api/v1/$batch",
        headers={"X-API-Key": token},
        json={
            "requests": [
                {
                    "id": "conflict",
                    "method": "POST",
                    "url": "/users",
                    "body": {
                        "email": seed_identity.member.email,
                        "displayName": "Duplicate",
                        "passwordProfile": _password_profile(),
                    },
                },
                {
                    "id": "dependent-update",
                    "method": "PATCH",
                    "url": f"/users/{orphan.id}",
                    "body": {"display_name": "Should Not Apply"},
                    "dependsOn": ["conflict"],
                },
            ]
        },
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    statuses = {item["id"]: item["status"] for item in payload["responses"]}
    assert statuses["conflict"] == 409
    assert statuses["dependent-update"] == 424

    orphan_get = await async_client.get(
        f"/api/v1/users/{orphan.id}",
        headers={"X-API-Key": token},
    )
    assert orphan_get.status_code == 200, orphan_get.text
    orphan_payload = orphan_get.json()
    assert "display_name" not in orphan_payload


async def test_batch_permissions_are_enforced_per_subrequest(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.post(
        "/api/v1/$batch",
        headers={"X-API-Key": token},
        json={
            "requests": [
                {
                    "id": "deny",
                    "method": "PATCH",
                    "url": f"/users/{seed_identity.orphan.id}",
                    "body": {"department": "Denied"},
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["responses"][0]["status"] == 403
    assert payload["responses"][0]["body"]["detail"] == "Global users.manage_all permission required."


async def test_workspace_owner_cannot_use_batch_for_global_user_mutations(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    owner = seed_identity.workspace_owner
    token, _ = await login(async_client, email=owner.email, password=owner.password)

    response = await async_client.post(
        "/api/v1/$batch",
        headers={"X-API-Key": token},
        json={
            "requests": [
                {
                    "id": "owner-deny",
                    "method": "POST",
                    "url": "/users",
                    "body": {
                        "email": f"owner-denied-{uuid4().hex[:8]}@example.com",
                        "passwordProfile": _password_profile(),
                    },
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["responses"][0]["status"] == 403


async def test_batch_rejects_unknown_dependency_ids(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.post(
        "/api/v1/$batch",
        headers={"X-API-Key": token},
        json={
            "requests": [
                {
                    "id": "one",
                    "method": "POST",
                    "url": "/users",
                    "body": {
                        "email": f"unknown-dep-{uuid4().hex[:8]}@example.com",
                        "passwordProfile": _password_profile(),
                    },
                    "dependsOn": ["missing-id"],
                }
            ]
        },
    )
    assert response.status_code == 422, response.text
    assert "Unknown dependency id" in str(response.json()["detail"])


async def test_batch_rejects_more_than_twenty_subrequests(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    requests = [
        {
            "id": f"req-{index}",
            "method": "PATCH",
            "url": f"/users/{seed_identity.member.id}",
            "body": {"department": f"Batch {index}"},
        }
        for index in range(21)
    ]
    response = await async_client.post(
        "/api/v1/$batch",
        headers={"X-API-Key": token},
        json={"requests": requests},
    )
    assert response.status_code == 422, response.text
