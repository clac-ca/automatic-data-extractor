"""Workspaces service behaviour tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.features.workspaces.models import WorkspaceMembership, WorkspaceRole
from app.features.workspaces.service import WorkspacesService

pytestmark = pytest.mark.asyncio


async def test_update_member_role_blocks_last_owner_demotion(
    seed_identity: dict[str, object],
) -> None:
    """A workspace must always retain at least one owner."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        service = WorkspacesService(session=session)
        workspace_id = seed_identity["workspace_id"]
        owner_id = seed_identity["workspace_owner"]["id"]  # type: ignore[index]

        result = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == owner_id,
            )
        )
        owner_membership = result.scalar_one()

        with pytest.raises(HTTPException) as exc:
            await service.update_member_role(
                workspace_id=workspace_id,
                membership_id=owner_membership.id,
                role=WorkspaceRole.MEMBER,
            )

        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
