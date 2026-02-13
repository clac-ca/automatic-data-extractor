from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from uuid import UUID

from ade_db.models import (
    AssignmentScopeType,
    Invitation,
    InvitationStatus,
    PrincipalType,
    Role,
    RoleAssignment,
    User,
)
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


def _items(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("items")
    return raw if isinstance(raw, list) else []


def _workspace_member_role_id(db_session: Session) -> str:
    stmt = select(Role.id).where(Role.slug == "workspace-member").limit(1)
    role_id = db_session.execute(stmt).scalar_one_or_none()
    assert role_id is not None
    return str(role_id)


async def test_workspace_owner_can_invite_unknown_user_with_workspace_role(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    token, _ = await login(async_client, email=owner.email, password=owner.password)

    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    invite_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "invite-unknown@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": token},
    )
    assert invite_response.status_code == 201, invite_response.text
    payload = invite_response.json()
    invited_user_id = payload["invited_user_id"]
    assert isinstance(invited_user_id, str) and invited_user_id
    assert payload["status"] == "pending"
    assert payload["workspace_id"] == str(seed_identity.workspace_id)
    assert payload["workspaceContext"]["workspaceId"] == str(seed_identity.workspace_id)
    assert payload["workspaceContext"]["roleAssignments"] == [{"roleId": workspace_member_role_id}]

    assignments_response = await async_client.get(
        f"/api/v1/workspaces/{seed_identity.workspace_id}/roleAssignments",
        headers={"X-API-Key": token},
    )
    assert assignments_response.status_code == 200, assignments_response.text
    assignments = _items(assignments_response.json())
    assert any(
        item["principal_type"] == "user"
        and item["principal_id"] == invited_user_id
        and item["role_id"] == workspace_member_role_id
        for item in assignments
    )


async def test_workspace_owner_invite_existing_user_does_not_duplicate_identity(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    token, _ = await login(async_client, email=owner.email, password=owner.password)
    existing_email = seed_identity.orphan.email

    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    invite_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": existing_email,
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": token},
    )
    assert invite_response.status_code == 201, invite_response.text
    payload = invite_response.json()
    assert payload["invited_user_id"] == str(seed_identity.orphan.id)

    def _count_users_for_email() -> int:
        stmt = select(func.count()).select_from(User).where(
            User.email_normalized == existing_email.lower()
        )
        return int(db_session.execute(stmt).scalar_one() or 0)

    user_count = await anyio.to_thread.run_sync(_count_users_for_email)
    assert user_count == 1

    def _count_workspace_assignments() -> int:
        stmt = select(func.count()).select_from(RoleAssignment).where(
            RoleAssignment.principal_type == PrincipalType.USER,
            RoleAssignment.principal_id == seed_identity.orphan.id,
            RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
            RoleAssignment.scope_id == seed_identity.workspace_id,
        )
        return int(db_session.execute(stmt).scalar_one() or 0)

    assignment_count = await anyio.to_thread.run_sync(_count_workspace_assignments)
    assert assignment_count >= 1


async def test_invitation_list_enforces_workspace_scope_read_permissions(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    member = seed_identity.member
    member_token, _ = await login(async_client, email=member.email, password=member.password)

    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    create_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "visibility-check@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": owner_token},
    )
    assert create_response.status_code == 201, create_response.text

    owner_list = await async_client.get(
        "/api/v1/invitations",
        params={"workspace_id": str(seed_identity.workspace_id)},
        headers={"X-API-Key": owner_token},
    )
    assert owner_list.status_code == 200, owner_list.text
    emails = [item["email_normalized"] for item in owner_list.json().get("items", [])]
    assert "visibility-check@example.com" in emails

    member_list = await async_client.get(
        "/api/v1/invitations",
        params={"workspace_id": str(seed_identity.workspace_id)},
        headers={"X-API-Key": member_token},
    )
    assert member_list.status_code == 403


async def test_invitation_manage_actions_enforce_scope_permissions(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    member = seed_identity.member
    member_token, _ = await login(async_client, email=member.email, password=member.password)

    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    create_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "manage-check@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": owner_token},
    )
    assert create_response.status_code == 201, create_response.text
    invitation_id = create_response.json()["id"]

    forbidden_resend = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/resend",
        headers={"X-API-Key": member_token},
    )
    assert forbidden_resend.status_code == 403

    forbidden_cancel = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/cancel",
        headers={"X-API-Key": member_token},
    )
    assert forbidden_cancel.status_code == 403

    owner_resend = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/resend",
        headers={"X-API-Key": owner_token},
    )
    assert owner_resend.status_code == 200, owner_resend.text

    owner_cancel = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/cancel",
        headers={"X-API-Key": owner_token},
    )
    assert owner_cancel.status_code == 200, owner_cancel.text
    assert owner_cancel.json()["status"] == "cancelled"


async def test_invitation_with_missing_workspace_scope_is_forbidden_for_workspace_owner(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    create_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "missing-workspace-scope@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": owner_token},
    )
    assert create_response.status_code == 201, create_response.text
    invitation_id = create_response.json()["id"]
    invitation_uuid = UUID(invitation_id)

    invitation = db_session.get(Invitation, invitation_uuid)
    assert invitation is not None
    invitation.workspace_id = None
    db_session.flush()

    read_response = await async_client.get(
        f"/api/v1/invitations/{invitation_id}",
        headers={"X-API-Key": owner_token},
    )
    assert read_response.status_code == 403, read_response.text

    resend_response = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/resend",
        headers={"X-API-Key": owner_token},
    )
    assert resend_response.status_code == 403, resend_response.text

    cancel_response = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/cancel",
        headers={"X-API-Key": owner_token},
    )
    assert cancel_response.status_code == 403, cancel_response.text


async def test_pending_invitation_transitions_to_expired_and_filters_correctly(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    create_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "expire-transition@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": owner_token},
    )
    assert create_response.status_code == 201, create_response.text
    invitation_id = create_response.json()["id"]
    invitation_uuid = UUID(invitation_id)

    invitation = db_session.get(Invitation, invitation_uuid)
    assert invitation is not None
    invitation.status = InvitationStatus.PENDING
    invitation.expires_at = invitation.created_at
    db_session.flush()

    detail_response = await async_client.get(
        f"/api/v1/invitations/{invitation_id}",
        headers={"X-API-Key": owner_token},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "expired"

    expired_list = await async_client.get(
        "/api/v1/invitations",
        params={
            "workspace_id": str(seed_identity.workspace_id),
            "status": "expired",
        },
        headers={"X-API-Key": owner_token},
    )
    assert expired_list.status_code == 200, expired_list.text
    expired_ids = {item["id"] for item in expired_list.json().get("items", [])}
    assert invitation_id in expired_ids

    pending_list = await async_client.get(
        "/api/v1/invitations",
        params={
            "workspace_id": str(seed_identity.workspace_id),
            "status": "pending",
        },
        headers={"X-API-Key": owner_token},
    )
    assert pending_list.status_code == 200, pending_list.text
    pending_ids = {item["id"] for item in pending_list.json().get("items", [])}
    assert invitation_id not in pending_ids


async def test_resend_cancelled_invitation_returns_conflict_without_mutating_expiry(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    create_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "cancelled-resend@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": owner_token},
    )
    assert create_response.status_code == 201, create_response.text
    invitation_id = create_response.json()["id"]
    invitation_uuid = UUID(invitation_id)

    cancel_response = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/cancel",
        headers={"X-API-Key": owner_token},
    )
    assert cancel_response.status_code == 200, cancel_response.text

    db_session.expire_all()
    cancelled_invitation = db_session.get(Invitation, invitation_uuid)
    assert cancelled_invitation is not None
    assert cancelled_invitation.status == InvitationStatus.CANCELLED
    cancelled_expiry = cancelled_invitation.expires_at

    resend_response = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/resend",
        headers={"X-API-Key": owner_token},
    )
    assert resend_response.status_code == 409, resend_response.text

    db_session.expire_all()
    invitation_after = db_session.get(Invitation, invitation_uuid)
    assert invitation_after is not None
    assert invitation_after.status == InvitationStatus.CANCELLED
    assert invitation_after.expires_at == cancelled_expiry


async def test_read_paths_do_not_mutate_updated_at_for_effectively_expired_invitation(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    create_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "readonly-expired@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": owner_token},
    )
    assert create_response.status_code == 201, create_response.text
    invitation_id = create_response.json()["id"]
    invitation_uuid = UUID(invitation_id)

    invitation = db_session.get(Invitation, invitation_uuid)
    assert invitation is not None
    invitation.status = InvitationStatus.PENDING
    invitation.expires_at = invitation.created_at
    db_session.flush()
    before_updated_at = invitation.updated_at

    detail_response = await async_client.get(
        f"/api/v1/invitations/{invitation_id}",
        headers={"X-API-Key": owner_token},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "expired"

    list_response = await async_client.get(
        "/api/v1/invitations",
        params={
            "workspace_id": str(seed_identity.workspace_id),
            "status": "expired",
        },
        headers={"X-API-Key": owner_token},
    )
    assert list_response.status_code == 200, list_response.text

    db_session.expire_all()
    invitation_after = db_session.get(Invitation, invitation_uuid)
    assert invitation_after is not None
    assert invitation_after.updated_at == before_updated_at


async def test_effectively_expired_invitation_allows_resend_and_cancel(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    create_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "expired-actions@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": owner_token},
    )
    assert create_response.status_code == 201, create_response.text
    invitation_id = create_response.json()["id"]
    invitation_uuid = UUID(invitation_id)

    invitation = db_session.get(Invitation, invitation_uuid)
    assert invitation is not None
    invitation.status = InvitationStatus.PENDING
    invitation.expires_at = invitation.created_at
    db_session.flush()

    resend_response = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/resend",
        headers={"X-API-Key": owner_token},
    )
    assert resend_response.status_code == 200, resend_response.text
    assert resend_response.json()["status"] == "pending"

    invitation = db_session.get(Invitation, invitation_uuid)
    assert invitation is not None
    invitation.status = InvitationStatus.PENDING
    invitation.expires_at = invitation.created_at
    db_session.flush()

    cancel_response = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/cancel",
        headers={"X-API-Key": owner_token},
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["status"] == "cancelled"


async def test_resend_and_cancel_accepted_invitation_return_conflict(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    create_response = await async_client.post(
        "/api/v1/invitations",
        json={
            "invitedUserEmail": "accepted-conflict@example.com",
            "workspaceContext": {
                "workspaceId": str(seed_identity.workspace_id),
                "roleAssignments": [{"roleId": workspace_member_role_id}],
            },
        },
        headers={"X-API-Key": owner_token},
    )
    assert create_response.status_code == 201, create_response.text
    invitation_id = create_response.json()["id"]
    invitation_uuid = UUID(invitation_id)

    invitation = db_session.get(Invitation, invitation_uuid)
    assert invitation is not None
    invitation.status = InvitationStatus.ACCEPTED
    db_session.flush()

    resend_response = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/resend",
        headers={"X-API-Key": owner_token},
    )
    assert resend_response.status_code == 409, resend_response.text

    cancel_response = await async_client.post(
        f"/api/v1/invitations/{invitation_id}/cancel",
        headers={"X-API-Key": owner_token},
    )
    assert cancel_response.status_code == 409, cancel_response.text


async def test_invitation_list_supports_cursor_pagination_and_search(
    async_client: AsyncClient,
    seed_identity,
    db_session: Session,
) -> None:
    owner = seed_identity.workspace_owner
    owner_token, _ = await login(async_client, email=owner.email, password=owner.password)
    workspace_member_role_id = await anyio.to_thread.run_sync(
        _workspace_member_role_id,
        db_session,
    )

    for email in [
        "cursor-a@example.com",
        "cursor-b@example.com",
        "cursor-c@example.com",
    ]:
        create_response = await async_client.post(
            "/api/v1/invitations",
            json={
                "invitedUserEmail": email,
                "workspaceContext": {
                    "workspaceId": str(seed_identity.workspace_id),
                    "roleAssignments": [{"roleId": workspace_member_role_id}],
                },
            },
            headers={"X-API-Key": owner_token},
        )
        assert create_response.status_code == 201, create_response.text

    first_page = await async_client.get(
        "/api/v1/invitations",
        params={
            "workspace_id": str(seed_identity.workspace_id),
            "limit": 2,
            "includeTotal": True,
        },
        headers={"X-API-Key": owner_token},
    )
    assert first_page.status_code == 200, first_page.text
    first_payload = first_page.json()
    first_items = first_payload.get("items", [])
    assert isinstance(first_items, list)
    assert len(first_items) == 2
    first_meta = first_payload.get("meta", {})
    assert first_meta.get("hasMore") is True
    assert isinstance(first_meta.get("nextCursor"), str)
    assert first_meta.get("totalIncluded") is True
    assert int(first_meta.get("totalCount") or 0) >= 3

    second_page = await async_client.get(
        "/api/v1/invitations",
        params={
            "workspace_id": str(seed_identity.workspace_id),
            "limit": 2,
            "cursor": first_meta["nextCursor"],
        },
        headers={"X-API-Key": owner_token},
    )
    assert second_page.status_code == 200, second_page.text
    second_payload = second_page.json()
    second_items = second_payload.get("items", [])
    assert isinstance(second_items, list)
    assert second_items

    first_ids = {item["id"] for item in first_items}
    second_ids = {item["id"] for item in second_items}
    assert first_ids.isdisjoint(second_ids)

    searched = await async_client.get(
        "/api/v1/invitations",
        params={
            "workspace_id": str(seed_identity.workspace_id),
            "q": "cursor-b",
            "limit": 10,
        },
        headers={"X-API-Key": owner_token},
    )
    assert searched.status_code == 200, searched.text
    searched_items = searched.json().get("items", [])
    assert isinstance(searched_items, list)
    assert any(item["email_normalized"] == "cursor-b@example.com" for item in searched_items)
