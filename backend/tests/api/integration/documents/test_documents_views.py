"""Saved document views integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_db.models import DocumentView
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


def build_view_payload(*, name: str, visibility: str = "private") -> dict:
    return {
        "name": name,
        "visibility": visibility,
        "queryState": {
            "lifecycle": "active",
            "q": None,
            "sort": [{"id": "createdAt", "desc": True}],
            "filters": [],
            "joinOperator": "and",
        },
        "tableState": {
            "columnVisibility": {"id": False},
            "columnOrder": ["name", "createdAt"],
        },
    }


async def _headers(async_client: AsyncClient, *, email: str, password: str) -> dict[str, str]:
    token, _ = await login(async_client, email=email, password=password)
    return {"X-API-Key": token}


async def test_list_document_views_includes_default_system_views(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    member = seed_identity.member
    headers = await _headers(async_client, email=member.email, password=member.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    response = await async_client.get(f"{workspace_base}/documents/views", headers=headers)

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    system_keys = {item["systemKey"] for item in items if item["visibility"] == "system"}
    assert system_keys == {"all_documents", "assigned_to_me", "unassigned", "deleted"}

    by_key = {
        item["systemKey"]: item
        for item in items
        if item["visibility"] == "system" and item["systemKey"]
    }
    assert by_key["assigned_to_me"]["queryState"]["simpleFilters"] == {"assigneeId": ["me"]}
    assert by_key["assigned_to_me"]["queryState"]["filters"] == []
    assert by_key["unassigned"]["queryState"]["simpleFilters"] == {
        "assigneeId": ["__empty__"]
    }
    assert by_key["unassigned"]["queryState"]["filters"] == []

    persisted = list(
        db_session.execute(
            select(DocumentView).where(
                DocumentView.workspace_id == seed_identity.workspace_id
            )
        ).scalars()
    )
    assert all(view.visibility.value in {"public", "private"} for view in persisted)


async def test_private_view_crud_is_owner_scoped(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    owner = seed_identity.workspace_owner
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    member_headers = await _headers(async_client, email=member.email, password=member.password)
    owner_headers = await _headers(async_client, email=owner.email, password=owner.password)

    create = await async_client.post(
        f"{workspace_base}/documents/views",
        headers=member_headers,
        json=build_view_payload(name="My triage", visibility="private"),
    )
    assert create.status_code == 201, create.text
    view_id = create.json()["id"]

    owner_patch = await async_client.patch(
        f"{workspace_base}/documents/views/{view_id}",
        headers=owner_headers,
        json={"name": "Owner cannot edit"},
    )
    assert owner_patch.status_code == 404, owner_patch.text

    member_patch = await async_client.patch(
        f"{workspace_base}/documents/views/{view_id}",
        headers=member_headers,
        json={"name": "My triage updated"},
    )
    assert member_patch.status_code == 200, member_patch.text
    assert member_patch.json()["name"] == "My triage updated"

    member_delete = await async_client.delete(
        f"{workspace_base}/documents/views/{view_id}",
        headers=member_headers,
    )
    assert member_delete.status_code == 204, member_delete.text


async def test_public_view_requires_public_manage_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    member = seed_identity.member
    owner = seed_identity.workspace_owner
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    member_headers = await _headers(async_client, email=member.email, password=member.password)
    owner_headers = await _headers(async_client, email=owner.email, password=owner.password)

    member_create_public = await async_client.post(
        f"{workspace_base}/documents/views",
        headers=member_headers,
        json=build_view_payload(name="Shared queue", visibility="public"),
    )
    assert member_create_public.status_code == 403, member_create_public.text

    owner_create_public = await async_client.post(
        f"{workspace_base}/documents/views",
        headers=owner_headers,
        json=build_view_payload(name="Shared queue", visibility="public"),
    )
    assert owner_create_public.status_code == 201, owner_create_public.text
    public_view_id = owner_create_public.json()["id"]

    member_patch_public = await async_client.patch(
        f"{workspace_base}/documents/views/{public_view_id}",
        headers=member_headers,
        json={"name": "Member update blocked"},
    )
    assert member_patch_public.status_code == 403, member_patch_public.text

    member_delete_public = await async_client.delete(
        f"{workspace_base}/documents/views/{public_view_id}",
        headers=member_headers,
    )
    assert member_delete_public.status_code == 403, member_delete_public.text

    owner_patch_public = await async_client.patch(
        f"{workspace_base}/documents/views/{public_view_id}",
        headers=owner_headers,
        json={"name": "Shared queue updated"},
    )
    assert owner_patch_public.status_code == 200, owner_patch_public.text
    assert owner_patch_public.json()["name"] == "Shared queue updated"

    owner_delete_public = await async_client.delete(
        f"{workspace_base}/documents/views/{public_view_id}",
        headers=owner_headers,
    )
    assert owner_delete_public.status_code == 204, owner_delete_public.text


async def test_system_views_are_immutable(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    owner = seed_identity.workspace_owner
    headers = await _headers(async_client, email=owner.email, password=owner.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    listed = await async_client.get(f"{workspace_base}/documents/views", headers=headers)
    assert listed.status_code == 200, listed.text
    all_documents_view = next(
        item for item in listed.json()["items"] if item["systemKey"] == "all_documents"
    )
    system_view_id = all_documents_view["id"]

    patch = await async_client.patch(
        f"{workspace_base}/documents/views/{system_view_id}",
        headers=headers,
        json={"name": "Cannot rename"},
    )
    assert patch.status_code == 403, patch.text

    delete = await async_client.delete(
        f"{workspace_base}/documents/views/{system_view_id}",
        headers=headers,
    )
    assert delete.status_code == 403, delete.text


async def test_mutating_unknown_non_system_view_returns_not_found(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    owner = seed_identity.workspace_owner
    headers = await _headers(async_client, email=owner.email, password=owner.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"
    unknown_id = uuid4()

    patch = await async_client.patch(
        f"{workspace_base}/documents/views/{unknown_id}",
        headers=headers,
        json={"name": "Nope"},
    )
    assert patch.status_code == 404, patch.text

    delete = await async_client.delete(
        f"{workspace_base}/documents/views/{unknown_id}",
        headers=headers,
    )
    assert delete.status_code == 404, delete.text


@pytest.mark.parametrize("reserved_name", ["All documents", "Assigned to me", "Unassigned", "Deleted"])
async def test_reserved_system_names_are_blocked_on_create(
    async_client: AsyncClient,
    seed_identity,
    reserved_name: str,
) -> None:
    owner = seed_identity.workspace_owner
    headers = await _headers(async_client, email=owner.email, password=owner.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    response = await async_client.post(
        f"{workspace_base}/documents/views",
        headers=headers,
        json=build_view_payload(name=reserved_name, visibility="private"),
    )
    assert response.status_code == 409, response.text


async def test_reserved_system_names_are_blocked_on_update(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    owner = seed_identity.workspace_owner
    headers = await _headers(async_client, email=owner.email, password=owner.password)
    workspace_base = f"/api/v1/workspaces/{seed_identity.workspace_id}"

    created = await async_client.post(
        f"{workspace_base}/documents/views",
        headers=headers,
        json=build_view_payload(name="Needs rename", visibility="private"),
    )
    assert created.status_code == 201, created.text
    view_id = created.json()["id"]

    update = await async_client.patch(
        f"{workspace_base}/documents/views/{view_id}",
        headers=headers,
        json={"name": "Deleted"},
    )
    assert update.status_code == 409, update.text
