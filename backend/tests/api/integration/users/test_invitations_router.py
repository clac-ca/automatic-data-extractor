from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ade_db.models import (
    AssignmentScopeType,
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
