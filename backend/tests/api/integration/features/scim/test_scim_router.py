from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from ade_db.models import Group, GroupMembership, User
from tests.api.utils import login

pytestmark = pytest.mark.asyncio

_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
_ENTERPRISE_USER_SCHEMA = "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"


async def _admin_headers(async_client: AsyncClient, seed_identity) -> dict[str, str]:
    admin = seed_identity.admin
    api_key, _ = await login(async_client, email=admin.email, password=admin.password)
    return {"X-API-Key": api_key}


async def _set_provisioning_mode(
    async_client: AsyncClient,
    *,
    admin_headers: dict[str, str],
    mode: str,
) -> None:
    current = await async_client.get("/api/v1/admin/settings", headers=admin_headers)
    assert current.status_code == 200, current.text
    revision = current.json()["revision"]

    updated = await async_client.patch(
        "/api/v1/admin/settings",
        headers=admin_headers,
        json={
            "revision": revision,
            "changes": {
                "auth": {
                    "identityProvider": {
                        "provisioningMode": mode,
                    }
                }
            },
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["values"]["auth"]["identityProvider"]["provisioningMode"] == mode


async def _create_scim_token(
    async_client: AsyncClient,
    *,
    admin_headers: dict[str, str],
) -> tuple[str, UUID]:
    response = await async_client.post(
        "/api/v1/admin/scim/tokens",
        headers=admin_headers,
        json={"name": "SCIM integration"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["token"], UUID(payload["item"]["id"])


async def test_scim_endpoints_are_gated_by_provisioning_mode(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    headers = await _admin_headers(async_client, seed_identity)
    token, token_id = await _create_scim_token(async_client, admin_headers=headers)

    disabled = await async_client.get(
        "/scim/v2/ServiceProviderConfig",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert disabled.status_code == 404, disabled.text
    assert disabled.headers.get("content-type", "").startswith("application/scim+json")

    await _set_provisioning_mode(async_client, admin_headers=headers, mode="scim")

    enabled = await async_client.get(
        "/scim/v2/ServiceProviderConfig",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.headers.get("content-type", "").startswith("application/scim+json")
    assert enabled.json()["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"]

    revoke = await async_client.post(
        f"/api/v1/admin/scim/tokens/{token_id}/revoke",
        headers=headers,
    )
    assert revoke.status_code == 200, revoke.text

    revoked = await async_client.get(
        "/scim/v2/ServiceProviderConfig",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoked.status_code == 401, revoked.text
    assert revoked.headers.get("content-type", "").startswith("application/scim+json")


async def test_scim_user_and_group_provisioning_flow(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    headers = await _admin_headers(async_client, seed_identity)
    await _set_provisioning_mode(async_client, admin_headers=headers, mode="scim")
    token, _token_id = await _create_scim_token(async_client, admin_headers=headers)
    scim_headers = {"Authorization": f"Bearer {token}"}

    create_user = await async_client.post(
        "/scim/v2/Users",
        headers=scim_headers,
        json={
            "schemas": [_USER_SCHEMA, _ENTERPRISE_USER_SCHEMA],
            "userName": "scim.user@example.com",
            "displayName": "SCIM User",
            "name": {"givenName": "SCIM", "familyName": "User"},
            "title": "Analyst",
            "externalId": "entra-user-1",
            "phoneNumbers": [
                {"type": "mobile", "value": "+1 555 111 1111"},
                {"type": "work", "value": "+1 555 222 2222"},
            ],
            _ENTERPRISE_USER_SCHEMA: {
                "department": "Security",
                "employeeNumber": "E-100",
            },
            "active": True,
        },
    )
    assert create_user.status_code == 201, create_user.text
    user_payload = create_user.json()
    user_id = UUID(user_payload["id"])
    assert user_payload["userName"] == "scim.user@example.com"

    list_filtered = await async_client.get(
        "/scim/v2/Users",
        headers=scim_headers,
        params={"filter": 'userName eq "scim.user@example.com"'},
    )
    assert list_filtered.status_code == 200, list_filtered.text
    assert list_filtered.json()["totalResults"] == 1

    deactivate = await async_client.patch(
        f"/scim/v2/Users/{user_id}",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        },
    )
    assert deactivate.status_code == 200, deactivate.text
    assert deactivate.json()["active"] is False

    db_user = db_session.get(User, user_id)
    assert db_user is not None
    assert db_user.is_active is False
    assert db_user.source == "scim"

    create_group = await async_client.post(
        "/scim/v2/Groups",
        headers=scim_headers,
        json={
            "schemas": [_GROUP_SCHEMA],
            "displayName": "SCIM Group",
            "externalId": "entra-group-1",
            "members": [{"value": str(user_id)}],
        },
    )
    assert create_group.status_code == 201, create_group.text
    group_payload = create_group.json()
    group_id = UUID(group_payload["id"])
    assert group_payload["displayName"] == "SCIM Group"
    assert any(member["value"] == str(user_id) for member in group_payload.get("members", []))

    db_group = db_session.get(Group, group_id)
    assert db_group is not None
    memberships = list(
        db_session.query(GroupMembership)
        .filter(GroupMembership.group_id == group_id)
        .all()
    )
    assert len(memberships) == 1
    assert memberships[0].user_id == user_id

    unknown_member = uuid4()
    invalid_patch = await async_client.patch(
        f"/scim/v2/Groups/{group_id}",
        headers=scim_headers,
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {
                    "op": "add",
                    "path": "members",
                    "value": [{"value": str(unknown_member)}],
                }
            ],
        },
    )
    assert invalid_patch.status_code == 400, invalid_patch.text
    error_payload = invalid_patch.json()
    assert error_payload["scimType"] == "invalidValue"
    assert "Unknown member ids" in error_payload["detail"]
