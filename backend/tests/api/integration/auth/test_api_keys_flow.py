from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_create_list_revoke_api_key(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    auth_header = {"X-API-Key": token}

    create = await async_client.post(
        "/api/v1/users/me/apikeys",
        json={"name": "CLI Key"},
        headers=auth_header,
    )
    assert create.status_code == 201, create.text
    create_payload = create.json()
    api_key_id = create_payload["id"]
    assert create_payload["secret"]

    list_response = await async_client.get(
        "/api/v1/users/me/apikeys",
        headers=auth_header,
    )
    assert list_response.status_code == 200, list_response.text
    list_payload = list_response.json()
    assert api_key_id in {item["id"] for item in list_payload["items"]}

    read_response = await async_client.get(
        f"/api/v1/users/me/apikeys/{api_key_id}",
        headers=auth_header,
    )
    assert read_response.status_code == 200, read_response.text
    etag = read_response.headers.get("ETag")
    assert etag

    revoke = await async_client.delete(
        f"/api/v1/users/me/apikeys/{api_key_id}",
        headers={**auth_header, "If-Match": etag},
    )
    assert revoke.status_code == 204, revoke.text


async def test_list_tenant_api_keys_requires_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        "/api/v1/apikeys",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 403


async def test_self_api_key_management_requires_manage_all_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, payload = await login(async_client, email=member.email, password=member.password)
    auth_header = {"X-API-Key": token}

    list_response = await async_client.get("/api/v1/users/me/apikeys", headers=auth_header)
    assert list_response.status_code == 403, list_response.text

    create_response = await async_client.post(
        "/api/v1/users/me/apikeys",
        json={"name": "Forbidden key"},
        headers=auth_header,
    )
    assert create_response.status_code == 403, create_response.text

    api_key_id = payload.get("id")
    assert isinstance(api_key_id, str) and api_key_id

    read_response = await async_client.get(
        f"/api/v1/users/me/apikeys/{api_key_id}",
        headers=auth_header,
    )
    assert read_response.status_code == 403, read_response.text

    revoke_response = await async_client.delete(
        f"/api/v1/users/me/apikeys/{api_key_id}",
        headers={**auth_header, "If-Match": "*"},
    )
    assert revoke_response.status_code == 403, revoke_response.text


async def test_list_tenant_api_keys_admin_supports_user_filter(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    member = seed_identity.member
    owner = seed_identity.workspace_owner
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    auth_header = {"X-API-Key": token}

    create_member_key = await async_client.post(
        f"/api/v1/users/{member.id}/apikeys",
        json={"name": "Member key"},
        headers=auth_header,
    )
    assert create_member_key.status_code == 201, create_member_key.text

    create_owner_key = await async_client.post(
        f"/api/v1/users/{owner.id}/apikeys",
        json={"name": "Owner key"},
        headers=auth_header,
    )
    assert create_owner_key.status_code == 201, create_owner_key.text

    list_response = await async_client.get("/api/v1/apikeys", headers=auth_header)
    assert list_response.status_code == 200, list_response.text
    all_keys = list_response.json()["items"]
    assert any(item["user_id"] == str(member.id) for item in all_keys)
    assert any(item["user_id"] == str(owner.id) for item in all_keys)

    filtered_response = await async_client.get(
        "/api/v1/apikeys",
        headers=auth_header,
        params={"userId": str(member.id)},
    )
    assert filtered_response.status_code == 200, filtered_response.text
    filtered_keys = filtered_response.json()["items"]
    assert filtered_keys
    assert all(item["user_id"] == str(member.id) for item in filtered_keys)


async def test_api_key_bearer_header_is_rejected(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    async_client.cookies.clear()

    response = await async_client.get(
        "/api/v1/me/bootstrap",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
