"""Unit tests for workspace service guardrails."""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.features.roles.models import Role
from app.features.workspaces.models import WorkspaceMembership
from app.features.workspaces.schemas import WorkspaceMemberRolesUpdate
from app.features.workspaces.service import WorkspacesService

pytestmark = pytest.mark.asyncio


async def test_assign_member_roles_blocks_last_governor(seed_identity: dict[str, object]) -> None:
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
        membership = result.scalar_one()

        with pytest.raises(HTTPException) as exc:
            await service.assign_member_roles(
                workspace_id=workspace_id,
                membership_id=membership.id,
                payload=WorkspaceMemberRolesUpdate(role_ids=[]),
            )

        assert exc.value.status_code == status.HTTP_409_CONFLICT


async def test_remove_member_blocks_last_governor(seed_identity: dict[str, object]) -> None:
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
        membership = result.scalar_one()

        with pytest.raises(HTTPException) as exc:
            await service.remove_member(
                workspace_id=workspace_id,
                membership_id=membership.id,
            )

        assert exc.value.status_code == status.HTTP_409_CONFLICT


async def test_assign_member_roles_allows_replacing_when_other_governor(
    seed_identity: dict[str, object]
) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        service = WorkspacesService(session=session)
        workspace_id = seed_identity["workspace_id"]
        owner_id = seed_identity["workspace_owner"]["id"]  # type: ignore[index]
        member_id = seed_identity["member"]["id"]  # type: ignore[index]

        # promote a member to owner to create a second governor
        owner_role = await session.scalar(select(Role).where(Role.slug == "workspace-owner"))
        assert owner_role is not None

        member_membership = await session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == member_id,
            )
        )
        assert member_membership is not None
        await service.assign_member_roles(
            workspace_id=workspace_id,
            membership_id=member_membership.id,
            payload=WorkspaceMemberRolesUpdate(role_ids=[owner_role.id]),
        )

        # now demote the original owner to a member; guard should allow it
        member_role = await session.scalar(select(Role).where(Role.slug == "workspace-member"))
        assert member_role is not None

        owner_membership = await session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == owner_id,
            )
        )
        assert owner_membership is not None

        await service.assign_member_roles(
            workspace_id=workspace_id,
            membership_id=owner_membership.id,
            payload=WorkspaceMemberRolesUpdate(role_ids=[member_role.id]),
        )

        refreshed_owner = await session.get(WorkspaceMembership, owner_membership.id)
        assert refreshed_owner is not None
        slugs = service._slugs_for_membership(refreshed_owner)
        assert slugs == ["workspace-member"]
