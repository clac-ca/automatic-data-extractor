from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_db.models import GroupMembership, GroupOwner, Role
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    return payload["items"]


def _role_id_by_slug(db_session: Session, slug: str) -> str:
    stmt = select(Role.id).where(Role.slug == slug).limit(1)
    role_id = db_session.execute(stmt).scalar_one_or_none()
    assert role_id is not None
    return str(role_id)


async def test_permission_catalog_requires_global_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        "/api/v1/permissions",
        params={
            "filters": json.dumps(
                [{"id": "scopeType", "operator": "eq", "value": "workspace"}]
            )
        },
        headers={"X-API-Key": token},
    )

    assert response.status_code == 403


async def test_permission_catalog_global_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        "/api/v1/permissions",
        params={
            "filters": json.dumps(
                [{"id": "scopeType", "operator": "eq", "value": "global"}]
            )
        },
        headers={"X-API-Key": token},
    )

    assert response.status_code == 200
    payload = response.json()
    records = _items(payload)
    keys = {entry["key"] for entry in records}
    assert "roles.read_all" in keys
    assert "users.read_all" in keys


async def test_roles_crud_and_delete(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    create_response = await async_client.post(
        "/api/v1/roles",
        json={
            "name": "Data Steward",
            "permissions": ["users.read_all"],
        },
        headers={"X-API-Key": token},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    role_id = created["id"]
    assert created["slug"] == "data-steward"
    assert created["permissions"] == ["users.read_all"]

    read_response = await async_client.get(
        f"/api/v1/roles/{role_id}",
        headers={"X-API-Key": token},
    )
    assert read_response.status_code == 200, read_response.text
    role_etag = read_response.headers.get("ETag")
    assert role_etag is not None

    update_response = await async_client.patch(
        f"/api/v1/roles/{role_id}",
        json={
            "name": "Data Steward",
            "description": "Manages user directory",
            "permissions": ["users.read_all", "roles.read_all"],
        },
        headers={
            "X-API-Key": token,
            "If-Match": role_etag,
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert sorted(updated["permissions"]) == ["roles.read_all", "users.read_all"]
    assert updated["description"] == "Manages user directory"
    updated_etag = update_response.headers.get("ETag")
    assert updated_etag is not None

    delete_response = await async_client.delete(
        f"/api/v1/roles/{role_id}",
        headers={
            "X-API-Key": token,
            "If-Match": updated_etag,
        },
    )
    assert delete_response.status_code == 204

    missing_response = await async_client.get(
        f"/api/v1/roles/{role_id}",
        headers={"X-API-Key": token},
    )
    assert missing_response.status_code == 404


async def test_workspace_role_assignment_listing_requires_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 403


async def test_workspace_role_assignment_listing_admin(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assignments = _items(payload)
    assert any(
        str(item["principal_id"]) == str(seed_identity.workspace_owner.id)
        and item["principal_type"] == "user"
        for item in assignments
    )


async def test_organization_role_assignment_listing_supports_pagination_and_filters(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    first_page = await async_client.get(
        "/api/v1/roleAssignments",
        params={
            "limit": 2,
            "sort": json.dumps([{"id": "createdAt", "desc": True}]),
            "includeTotal": "true",
        },
        headers={"X-API-Key": token},
    )
    assert first_page.status_code == 200, first_page.text
    first_payload = first_page.json()
    first_items = _items(first_payload)
    assert len(first_items) == 2
    assert first_payload["meta"]["hasMore"] is True
    assert first_payload["meta"]["nextCursor"] is not None
    assert first_payload["meta"]["totalIncluded"] is True
    assert isinstance(first_payload["meta"]["totalCount"], int)

    second_page = await async_client.get(
        "/api/v1/roleAssignments",
        params={
            "limit": 2,
            "sort": json.dumps([{"id": "createdAt", "desc": True}]),
            "cursor": first_payload["meta"]["nextCursor"],
        },
        headers={"X-API-Key": token},
    )
    assert second_page.status_code == 200, second_page.text
    second_payload = second_page.json()
    second_items = _items(second_payload)
    assert second_items
    first_ids = {item["id"] for item in first_items}
    second_ids = {item["id"] for item in second_items}
    assert first_ids.isdisjoint(second_ids)

    filtered = await async_client.get(
        "/api/v1/roleAssignments",
        params={
            "filters": json.dumps([
                {"id": "principalId", "operator": "eq", "value": str(seed_identity.orphan.id)},
                {"id": "scopeType", "operator": "eq", "value": "organization"},
            ]),
            "includeTotal": "true",
        },
        headers={"X-API-Key": token},
    )
    assert filtered.status_code == 200, filtered.text
    filtered_items = _items(filtered.json())
    assert filtered_items
    assert all(str(item["principal_id"]) == str(seed_identity.orphan.id) for item in filtered_items)
    assert all(item["scope_type"] == "organization" for item in filtered_items)


async def test_workspace_role_assignment_listing_supports_pagination_and_filters(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    first_page = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        params={
            "limit": 1,
            "sort": json.dumps([{"id": "createdAt", "desc": True}]),
            "includeTotal": "true",
        },
        headers={"X-API-Key": token},
    )
    assert first_page.status_code == 200, first_page.text
    first_payload = first_page.json()
    first_items = _items(first_payload)
    assert len(first_items) == 1
    assert first_payload["meta"]["hasMore"] is True
    assert first_payload["meta"]["nextCursor"] is not None

    second_page = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        params={
            "limit": 1,
            "sort": json.dumps([{"id": "createdAt", "desc": True}]),
            "cursor": first_payload["meta"]["nextCursor"],
        },
        headers={"X-API-Key": token},
    )
    assert second_page.status_code == 200, second_page.text
    second_items = _items(second_page.json())
    assert second_items
    assert first_items[0]["id"] != second_items[0]["id"]

    filtered = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        params={
            "filters": json.dumps([
                {"id": "principalId", "operator": "eq", "value": str(seed_identity.workspace_owner.id)},
                {"id": "scopeType", "operator": "eq", "value": "workspace"},
            ]),
            "includeTotal": "true",
        },
        headers={"X-API-Key": token},
    )
    assert filtered.status_code == 200, filtered.text
    filtered_items = _items(filtered.json())
    assert filtered_items
    assert all(str(item["principal_id"]) == str(seed_identity.workspace_owner.id) for item in filtered_items)
    assert all(item["scope_type"] == "workspace" for item in filtered_items)


async def test_role_assignment_listing_rejects_unknown_query_params(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)

    response = await async_client.get(
        "/api/v1/roleAssignments",
        params={"workspaceId": str(seed_identity.workspace_id)},
        headers={"X-API-Key": token},
    )
    assert response.status_code == 422, response.text
    payload = response.json()
    errors = payload.get("errors")
    assert isinstance(errors, list)
    assert any(item.get("path") == "workspaceId" for item in errors)


async def test_workspace_owner_can_manage_workspace_assignments_but_not_org_assignments(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    workspace_member_role_id = _role_id_by_slug(db_session, "workspace-member")
    global_user_role_id = _role_id_by_slug(db_session, "global-user")

    workspace_list = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        headers={"X-API-Key": owner_token},
    )
    assert workspace_list.status_code == 200, workspace_list.text

    workspace_create = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        json={
            "principal_type": "user",
            "principal_id": str(seed_identity.orphan.id),
            "role_id": workspace_member_role_id,
        },
        headers={"X-API-Key": owner_token},
    )
    assert workspace_create.status_code == 201, workspace_create.text

    org_create = await async_client.post(
        "/api/v1/roleAssignments",
        json={
            "principal_type": "user",
            "principal_id": str(seed_identity.orphan.id),
            "role_id": global_user_role_id,
        },
        headers={"X-API-Key": owner_token},
    )
    assert org_create.status_code == 403


async def test_assign_workspace_principal_roles(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    workspace_id = seed_identity.workspace_id
    user_id = seed_identity.orphan.id
    user_id_str = str(user_id)

    # Reject missing role_id payload.
    create_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roleAssignments",
        json={
            "principal_type": "user",
            "principal_id": user_id_str,
        },
        headers={"X-API-Key": token},
    )
    assert create_response.status_code == 422

    # Load workspace-member role id
    roles_response = await async_client.get(
        "/api/v1/roles",
        params={
            "filters": json.dumps(
                [{"id": "scopeType", "operator": "eq", "value": "workspace"}]
            )
        },
        headers={"X-API-Key": token},
    )
    assert roles_response.status_code == 200
    workspace_roles = {role["slug"]: role["id"] for role in _items(roles_response.json())}
    member_role_id = workspace_roles["workspace-member"]

    create_assignment = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/roleAssignments",
        json={
            "principal_type": "user",
            "principal_id": user_id_str,
            "role_id": member_role_id,
        },
        headers={"X-API-Key": token},
    )
    assert create_assignment.status_code == 201, create_assignment.text
    created = create_assignment.json()
    assert created["principal_type"] == "user"
    assert str(created["principal_id"]) == user_id_str
    assert created["role_id"] == member_role_id
    assignment_id = created["id"]

    # Remove assignment
    delete_response = await async_client.delete(
        f"/api/v1/roleAssignments/{assignment_id}",
        headers={"X-API-Key": token},
    )
    assert delete_response.status_code == 204


async def test_group_workspace_assignment_grants_workspace_access(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    orphan = seed_identity.orphan

    roles_response = await async_client.get(
        "/api/v1/roles",
        params={
            "filters": json.dumps(
                [{"id": "scopeType", "operator": "eq", "value": "workspace"}]
            )
        },
        headers={"X-API-Key": admin_token},
    )
    assert roles_response.status_code == 200
    workspace_roles = {role["slug"]: role["id"] for role in _items(roles_response.json())}
    member_role_id = workspace_roles["workspace-member"]

    create_group_response = await async_client.post(
        "/api/v1/groups",
        json={
            "display_name": "Workspace Access Group",
            "slug": "workspace-access-group",
            "membership_mode": "assigned",
            "source": "internal",
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = UUID(create_group_response.json()["id"])

    add_member_response = await async_client.post(
        f"/api/v1/groups/{group_id}/members/$ref",
        json={"memberId": str(orphan.id)},
        headers={"X-API-Key": admin_token},
    )
    assert add_member_response.status_code == 200, add_member_response.text

    create_assignment = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        json={
            "principal_type": "group",
            "principal_id": str(group_id),
            "role_id": member_role_id,
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_assignment.status_code == 201, create_assignment.text

    orphan_token, _ = await login(async_client, email=orphan.email, password=orphan.password)

    list_workspaces = await async_client.get(
        "/api/v1/workspaces",
        headers={"X-API-Key": orphan_token},
    )
    assert list_workspaces.status_code == 200, list_workspaces.text
    listed_ids = {item["id"] for item in _items(list_workspaces.json())}
    assert str(seed_identity.workspace_id) in listed_ids

    read_workspace = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}",
        headers={"X-API-Key": orphan_token},
    )
    assert read_workspace.status_code == 200, read_workspace.text
    payload = read_workspace.json()
    assert "workspace-member" in payload["roles"]


async def _set_provisioning_mode(
    async_client: AsyncClient,
    *,
    admin_token: str,
    mode: str,
) -> None:
    headers = {"X-API-Key": admin_token}
    current = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert current.status_code == 200, current.text
    revision = current.json()["revision"]

    updated = await async_client.patch(
        "/api/v1/admin/settings",
        headers=headers,
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


async def test_idp_group_assignments_require_scim_mode(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    admin = seed_identity.admin
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    global_user_role_id = _role_id_by_slug(db_session, "global-user")

    create_group_response = await async_client.post(
        "/api/v1/groups",
        json={
            "display_name": "IdP Managed",
            "slug": "idp-managed-assignment",
            "membership_mode": "assigned",
            "source": "idp",
            "external_id": "entra-group-assignment",
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    await _set_provisioning_mode(async_client, admin_token=admin_token, mode="jit")

    blocked = await async_client.post(
        "/api/v1/roleAssignments",
        json={
            "principal_type": "group",
            "principal_id": str(group_id),
            "role_id": global_user_role_id,
        },
        headers={"X-API-Key": admin_token},
    )
    assert blocked.status_code == 422, blocked.text
    assert (
        blocked.json()["detail"]
        == "Provider-managed groups are SCIM-managed and can only be used for role assignment when provisioning mode is SCIM."
    )

    await _set_provisioning_mode(async_client, admin_token=admin_token, mode="scim")

    allowed = await async_client.post(
        "/api/v1/roleAssignments",
        json={
            "principal_type": "group",
            "principal_id": str(group_id),
            "role_id": global_user_role_id,
        },
        headers={"X-API-Key": admin_token},
    )
    assert allowed.status_code == 201, allowed.text


async def test_idp_group_workspace_grants_are_effective_only_in_scim_mode(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    admin = seed_identity.admin
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    orphan = seed_identity.orphan
    workspace_member_role_id = _role_id_by_slug(db_session, "workspace-member")

    create_group_response = await async_client.post(
        "/api/v1/groups",
        json={
            "display_name": "IdP Workspace Access",
            "slug": "idp-workspace-access",
            "membership_mode": "assigned",
            "source": "idp",
            "external_id": "entra-group-workspace",
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    db_session.add(
        GroupMembership(
            group_id=group_id,
            user_id=orphan.id,
            membership_source="idp",
        )
    )
    db_session.flush()

    await _set_provisioning_mode(async_client, admin_token=admin_token, mode="scim")

    assign_response = await async_client.post(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        json={
            "principal_type": "group",
            "principal_id": str(group_id),
            "role_id": workspace_member_role_id,
        },
        headers={"X-API-Key": admin_token},
    )
    assert assign_response.status_code == 201, assign_response.text

    orphan_token, _ = await login(async_client, email=orphan.email, password=orphan.password)

    workspaces_scim = await async_client.get(
        "/api/v1/workspaces",
        headers={"X-API-Key": orphan_token},
    )
    assert workspaces_scim.status_code == 200, workspaces_scim.text
    listed_scim = {item["id"] for item in _items(workspaces_scim.json())}
    assert str(seed_identity.workspace_id) in listed_scim

    await _set_provisioning_mode(async_client, admin_token=admin_token, mode="jit")

    workspaces_jit = await async_client.get(
        "/api/v1/workspaces",
        headers={"X-API-Key": orphan_token},
    )
    assert workspaces_jit.status_code == 200, workspaces_jit.text
    listed_jit = {item["id"] for item in _items(workspaces_jit.json())}
    assert str(seed_identity.workspace_id) not in listed_jit


async def test_provider_managed_group_memberships_are_read_only(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    admin = seed_identity.admin
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    orphan = seed_identity.orphan

    create_group_response = await async_client.post(
        "/api/v1/groups",
        json={
            "display_name": "Synced Directory Group",
            "slug": "synced-directory-group",
            "membership_mode": "assigned",
            "source": "idp",
            "external_id": "entra-group-1",
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    add_member_response = await async_client.post(
        f"/api/v1/groups/{group_id}/members/$ref",
        json={"memberId": str(orphan.id)},
        headers={"X-API-Key": admin_token},
    )
    assert add_member_response.status_code == 409, add_member_response.text
    assert (
        add_member_response.json()["detail"]
        == "Provider-managed group memberships are read-only"
    )

    db_session.add(
        GroupMembership(
            group_id=group_id,
            user_id=orphan.id,
            membership_source="idp",
        )
    )
    db_session.flush()

    remove_member_response = await async_client.delete(
        f"/api/v1/groups/{group_id}/members/{orphan.id}/$ref",
        headers={"X-API-Key": admin_token},
    )
    assert remove_member_response.status_code == 409, remove_member_response.text
    assert (
        remove_member_response.json()["detail"]
        == "Provider-managed group memberships are read-only"
    )


async def test_group_owners_crud_for_internal_group(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    orphan = seed_identity.orphan

    create_group_response = await async_client.post(
        "/api/v1/groups",
        json={
            "display_name": "Operations Admins",
            "slug": "operations-admins",
            "membership_mode": "assigned",
            "source": "internal",
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    add_owner_response = await async_client.post(
        f"/api/v1/groups/{group_id}/owners/$ref",
        json={"ownerId": str(orphan.id)},
        headers={"X-API-Key": admin_token},
    )
    assert add_owner_response.status_code == 200, add_owner_response.text
    owner_ids = {item["user_id"] for item in add_owner_response.json()["items"]}
    assert str(orphan.id) in owner_ids

    list_owners_response = await async_client.get(
        f"/api/v1/groups/{group_id}/owners",
        headers={"X-API-Key": admin_token},
    )
    assert list_owners_response.status_code == 200, list_owners_response.text
    listed_owner_ids = {item["user_id"] for item in list_owners_response.json()["items"]}
    assert str(orphan.id) in listed_owner_ids

    remove_owner_response = await async_client.delete(
        f"/api/v1/groups/{group_id}/owners/{orphan.id}/$ref",
        headers={"X-API-Key": admin_token},
    )
    assert remove_owner_response.status_code == 204, remove_owner_response.text

    list_after_remove = await async_client.get(
        f"/api/v1/groups/{group_id}/owners",
        headers={"X-API-Key": admin_token},
    )
    assert list_after_remove.status_code == 200, list_after_remove.text
    assert list_after_remove.json()["items"] == []


async def test_provider_managed_group_owners_are_read_only(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    admin = seed_identity.admin
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    orphan = seed_identity.orphan

    create_group_response = await async_client.post(
        "/api/v1/groups",
        json={
            "display_name": "Synced Owner Group",
            "slug": "synced-owner-group",
            "membership_mode": "assigned",
            "source": "idp",
            "external_id": "entra-owner-group-1",
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    add_owner_response = await async_client.post(
        f"/api/v1/groups/{group_id}/owners/$ref",
        json={"ownerId": str(orphan.id)},
        headers={"X-API-Key": admin_token},
    )
    assert add_owner_response.status_code == 409, add_owner_response.text
    assert (
        add_owner_response.json()["detail"]
        == "Provider-managed group memberships are read-only"
    )

    db_session.add(
        GroupOwner(
            group_id=group_id,
            user_id=orphan.id,
            ownership_source="idp",
        )
    )
    db_session.flush()

    remove_owner_response = await async_client.delete(
        f"/api/v1/groups/{group_id}/owners/{orphan.id}/$ref",
        headers={"X-API-Key": admin_token},
    )
    assert remove_owner_response.status_code == 409, remove_owner_response.text
    assert (
        remove_owner_response.json()["detail"]
        == "Provider-managed group memberships are read-only"
    )


async def test_group_owner_routes_require_permissions(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    admin = seed_identity.admin
    admin_token, _ = await login(async_client, email=admin.email, password=admin.password)
    member = seed_identity.member
    member_token, _ = await login(async_client, email=member.email, password=member.password)

    create_group_response = await async_client.post(
        "/api/v1/groups",
        json={
            "display_name": "Permission Check Group",
            "slug": "permission-check-group",
            "membership_mode": "assigned",
            "source": "internal",
        },
        headers={"X-API-Key": admin_token},
    )
    assert create_group_response.status_code == 201, create_group_response.text
    group_id = create_group_response.json()["id"]

    list_owners_response = await async_client.get(
        f"/api/v1/groups/{group_id}/owners",
        headers={"X-API-Key": member_token},
    )
    assert list_owners_response.status_code == 403, list_owners_response.text

    add_owner_response = await async_client.post(
        f"/api/v1/groups/{group_id}/owners/$ref",
        json={"ownerId": str(seed_identity.orphan.id)},
        headers={"X-API-Key": member_token},
    )
    assert add_owner_response.status_code == 403, add_owner_response.text

    remove_owner_response = await async_client.delete(
        f"/api/v1/groups/{group_id}/owners/{seed_identity.orphan.id}/$ref",
        headers={"X-API-Key": member_token},
    )
    assert remove_owner_response.status_code == 403, remove_owner_response.text
