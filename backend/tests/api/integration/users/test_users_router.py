"""User router tests."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_list_users_requires_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Non-admins should receive a 403 when listing users."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        "/api/v1/users",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 403


async def test_list_users_admin_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should see all registered users."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    emails: set[str] = set()
    cursor: str | None = None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        response = await async_client.get(
            "/api/v1/users",
            headers={"X-API-Key": token},
            params=params,
        )
        assert response.status_code == 200
        data = response.json()
        emails.update(item["email"] for item in data["items"])
        if not data["meta"]["hasMore"]:
            break
        cursor = data["meta"]["nextCursor"]
        assert cursor is not None
    expected = {
        seed_identity.admin.email,
        seed_identity.workspace_owner.email,
        seed_identity.member.email,
        seed_identity.member_with_manage.email,
        seed_identity.orphan.email,
    }
    assert expected.issubset(emails)


async def test_create_user_requires_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Non-admins should receive a 403 when creating users."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.post(
        "/api/v1/users",
        headers={"X-API-Key": token},
        json={
            "email": "new-user@example.com",
            "displayName": "New User",
            "passwordProfile": {
                "mode": "explicit",
                "password": "notsecret1!Ab",
                "forceChangeOnNextSignIn": False,
            },
        },
    )
    assert response.status_code == 403


async def test_create_user_admin_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should be able to pre-provision users."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.post(
        "/api/v1/users",
        headers={"X-API-Key": token},
        json={
            "email": "new-user@example.com",
            "displayName": " New User ",
            "passwordProfile": {
                "mode": "explicit",
                "password": "notsecret1!Ab",
                "forceChangeOnNextSignIn": False,
            },
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["user"]["email"] == "new-user@example.com"
    assert data["user"]["display_name"] == "New User"
    assert data["user"]["is_active"] is True
    assert data["user"]["is_service_account"] is False
    assert "global-user" in data["user"]["roles"]
    assert data["passwordProvisioning"]["mode"] == "explicit"
    assert "initialPassword" not in data["passwordProvisioning"]
    assert data["passwordProvisioning"]["forceChangeOnNextSignIn"] is False


async def test_create_user_conflict(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Creating a duplicate user should return HTTP 409."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.post(
        "/api/v1/users",
        headers={"X-API-Key": token},
        json={
            "email": seed_identity.member.email,
            "passwordProfile": {
                "mode": "explicit",
                "password": "notsecret1!Ab",
                "forceChangeOnNextSignIn": False,
            },
        },
    )
    assert response.status_code == 409


async def test_create_user_auto_generate_returns_one_time_password(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.post(
        "/api/v1/users",
        headers={"X-API-Key": token},
        json={
            "email": "generated-user@example.com",
            "displayName": "Generated User",
            "passwordProfile": {
                "mode": "auto_generate",
                "forceChangeOnNextSignIn": True,
            },
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["user"]["email"] == "generated-user@example.com"
    assert payload["passwordProvisioning"]["mode"] == "auto_generate"
    generated = payload["passwordProvisioning"]["initialPassword"]
    assert isinstance(generated, str)
    assert len(generated) >= 12
    assert payload["passwordProvisioning"]["forceChangeOnNextSignIn"] is True


async def test_get_user_requires_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Non-admins should not be able to fetch user details."""

    member = seed_identity.member
    target = seed_identity.admin
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        f"/api/v1/users/{target.id}",
        headers={"X-API-Key": token},
    )

    assert response.status_code == 403


async def test_get_user_admin_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should retrieve individual user profiles."""

    admin = seed_identity.admin
    target = seed_identity.member
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        f"/api/v1/users/{target.id}",
        headers={"X-API-Key": token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(target.id)
    assert data["email"] == target.email
    assert data["is_active"] is True
    assert "global-user" in data["roles"]
    assert isinstance(data["permissions"], list)


async def test_get_user_admin_not_found(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should receive 404 for unknown users."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        f"/api/v1/users/{uuid4()}",
        headers={"X-API-Key": token},
    )

    assert response.status_code == 404


async def test_update_user_requires_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Non-admins should not be able to mutate user records."""

    member = seed_identity.member
    target = seed_identity.orphan
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.patch(
        f"/api/v1/users/{target.id}",
        headers={"X-API-Key": token},
        json={"display_name": "Blocked"},
    )

    assert response.status_code == 403


async def test_update_user_admin_success(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Administrators should be able to update user status and metadata."""

    admin = seed_identity.admin
    target = seed_identity.orphan
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.patch(
        f"/api/v1/users/{target.id}",
        headers={"X-API-Key": token},
        json={"display_name": " Updated User ", "is_active": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Updated User"
    assert data["is_active"] is False

    confirm = await async_client.get(
        f"/api/v1/users/{target.id}",
        headers={"X-API-Key": token},
    )
    confirm_data = confirm.json()
    assert confirm_data["display_name"] == "Updated User"
    assert confirm_data["is_active"] is False


async def test_update_user_rejects_empty_payload(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """PATCH without fields should be rejected."""

    admin = seed_identity.admin
    target = seed_identity.member
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.patch(
        f"/api/v1/users/{target.id}",
        headers={"X-API-Key": token},
        json={},
    )
    assert response.status_code == 422


async def test_deactivate_user_revokes_api_keys(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Deactivation should set is_active false and revoke all owned API keys."""

    admin = seed_identity.admin
    target = seed_identity.member
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)

    create_key = await async_client.post(
        f"/api/v1/users/{target.id}/apikeys",
        headers={"X-API-Key": admin_token},
        json={"name": "Target key"},
    )
    assert create_key.status_code == 201, create_key.text
    secret = create_key.json()["secret"]

    preflight = await async_client.get(
        "/api/v1/me/bootstrap",
        headers={"X-API-Key": secret},
    )
    assert preflight.status_code == 200, preflight.text

    deactivate = await async_client.post(
        f"/api/v1/users/{target.id}/deactivate",
        headers={"X-API-Key": admin_token},
    )
    assert deactivate.status_code == 200, deactivate.text
    payload = deactivate.json()
    assert payload["is_active"] is False

    revoked_filters = json.dumps([{"id": "revokedAt", "operator": "isNotEmpty"}])
    key_list = await async_client.get(
        f"/api/v1/users/{target.id}/apikeys",
        headers={"X-API-Key": admin_token},
        params={"filters": revoked_filters},
    )
    assert key_list.status_code == 200, key_list.text
    records = key_list.json()["items"]
    assert records
    assert all(record["revoked_at"] is not None for record in records)

    denied = await async_client.get(
        "/api/v1/me/bootstrap",
        headers={"X-API-Key": secret},
    )
    assert denied.status_code == 401


async def test_deactivate_user_blocks_self(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Users should not be able to deactivate themselves."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.post(
        f"/api/v1/users/{admin.id}/deactivate",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 400


async def test_user_member_of_routes_manage_membership(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    target_user = seed_identity.orphan
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)

    create_group_response = await async_client.post(
        "/api/v1/groups",
        headers={"X-API-Key": admin_token},
        json={
            "display_name": "Finance Users",
            "slug": "finance-users",
            "membership_mode": "assigned",
            "source": "internal",
        },
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    add_member_of = await async_client.post(
        f"/api/v1/users/{target_user.id}/memberOf/$ref",
        headers={"X-API-Key": admin_token},
        json={"groupId": group_id},
    )
    assert add_member_of.status_code == 200, add_member_of.text
    added_items = add_member_of.json()["items"]
    assert any(
        item["group_id"] == group_id
        and item["is_member"] is True
        and item["is_owner"] is False
        for item in added_items
    )

    list_member_of = await async_client.get(
        f"/api/v1/users/{target_user.id}/memberOf",
        headers={"X-API-Key": admin_token},
    )
    assert list_member_of.status_code == 200, list_member_of.text
    listed_items = list_member_of.json()["items"]
    assert any(item["group_id"] == group_id for item in listed_items)

    remove_member_of = await async_client.delete(
        f"/api/v1/users/{target_user.id}/memberOf/{group_id}/$ref",
        headers={"X-API-Key": admin_token},
    )
    assert remove_member_of.status_code == 204, remove_member_of.text

    list_after_remove = await async_client.get(
        f"/api/v1/users/{target_user.id}/memberOf",
        headers={"X-API-Key": admin_token},
    )
    assert list_after_remove.status_code == 200, list_after_remove.text
    assert all(item["group_id"] != group_id for item in list_after_remove.json()["items"])


async def test_user_member_of_routes_require_permissions(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    member = seed_identity.member
    target_user = seed_identity.orphan
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    member_token, _ = await login(async_client, email=member.email, password=member.password)

    create_group_response = await async_client.post(
        "/api/v1/groups",
        headers={"X-API-Key": admin_token},
        json={
            "display_name": "Permission Locked Group",
            "slug": "permission-locked-group",
            "membership_mode": "assigned",
            "source": "internal",
        },
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    list_member_of = await async_client.get(
        f"/api/v1/users/{target_user.id}/memberOf",
        headers={"X-API-Key": member_token},
    )
    assert list_member_of.status_code == 403, list_member_of.text

    add_member_of = await async_client.post(
        f"/api/v1/users/{target_user.id}/memberOf/$ref",
        headers={"X-API-Key": member_token},
        json={"groupId": group_id},
    )
    assert add_member_of.status_code == 403, add_member_of.text

    remove_member_of = await async_client.delete(
        f"/api/v1/users/{target_user.id}/memberOf/{group_id}/$ref",
        headers={"X-API-Key": member_token},
    )
    assert remove_member_of.status_code == 403, remove_member_of.text


async def test_user_member_of_mutation_returns_conflict_for_provider_managed_group(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    target_user = seed_identity.orphan
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)

    create_group_response = await async_client.post(
        "/api/v1/groups",
        headers={"X-API-Key": admin_token},
        json={
            "display_name": "Synced Locked Group",
            "slug": "synced-locked-group",
            "membership_mode": "assigned",
            "source": "idp",
            "external_id": "provider-locked-1",
        },
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    add_member_of = await async_client.post(
        f"/api/v1/users/{target_user.id}/memberOf/$ref",
        headers={"X-API-Key": admin_token},
        json={"groupId": group_id},
    )
    assert add_member_of.status_code == 409, add_member_of.text
    assert add_member_of.json()["detail"] == "Provider-managed group memberships are read-only"
