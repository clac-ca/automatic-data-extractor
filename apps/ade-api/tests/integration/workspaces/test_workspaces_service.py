"""Unit tests for workspace service guardrails."""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from sqlalchemy import select

from ade_api.features.roles.models import Role
from ade_api.features.workspaces.models import Workspace, WorkspaceMembership
from ade_api.features.workspaces.schemas import WorkspaceMemberRolesUpdate
from ade_api.features.workspaces.service import WorkspacesService
from ade_api.shared.db.session import get_sessionmaker

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
        summaries = await service._summaries_for_workspace(
            workspace_id, [refreshed_owner]
        )
        summary = service._summary_for_membership(
            membership=refreshed_owner, summaries=summaries
        )
        member_view = service.build_member(
            refreshed_owner, summary=summary
        )
        assert member_view.roles == ["workspace-member"]


async def test_workspace_settings_mutation_persists(seed_identity: dict[str, object]) -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace_id = seed_identity["workspace_id"]
        workspace = await session.get(Workspace, workspace_id)
        assert workspace is not None

        workspace.settings["notifications"] = {"email": True}
        await session.flush()
        await session.refresh(workspace)

        reloaded = await session.get(Workspace, workspace_id)
        assert reloaded is not None
        assert reloaded.settings["notifications"]["email"] is True
