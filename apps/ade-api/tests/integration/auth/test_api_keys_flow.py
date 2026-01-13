from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_create_list_revoke_api_key(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    auth_header = {"Authorization": f"Bearer {token}"}

    create = await async_client.post(
        "/api/v1/users/me/apikeys",
        json={"name": "CLI Key"},
        headers={**auth_header, "Idempotency-Key": "test-api-key-1"},
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
