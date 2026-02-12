from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_api.core.security import hash_opaque_token
from ade_db.models import ScimToken
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_admin_scim_tokens_lifecycle(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    admin = seed_identity.admin
    api_key, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": api_key}

    initial = await async_client.get("/api/v1/admin/scim/tokens", headers=headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["items"] == []

    created = await async_client.post(
        "/api/v1/admin/scim/tokens",
        headers=headers,
        json={"name": "Entra provisioning"},
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["token"].startswith("scim_")
    assert payload["item"]["name"] == "Entra provisioning"

    token_id = UUID(payload["item"]["id"])
    token_plaintext = payload["token"]

    db_row = db_session.execute(select(ScimToken).where(ScimToken.id == token_id)).scalar_one()
    assert db_row.hashed_secret == hash_opaque_token(token_plaintext)
    assert db_row.hashed_secret != token_plaintext
    assert db_row.revoked_at is None

    listed = await async_client.get("/api/v1/admin/scim/tokens", headers=headers)
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(token_id)
    assert "token" not in items[0]

    revoked = await async_client.post(
        f"/api/v1/admin/scim/tokens/{token_id}/revoke",
        headers=headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revokedAt"] is not None


async def test_admin_scim_tokens_require_system_settings_permissions(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    api_key, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        "/api/v1/admin/scim/tokens",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 403, response.text
