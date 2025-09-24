"""Workspace persistence helpers."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Workspace, WorkspaceMembership, WorkspaceRole


class WorkspacesRepository:
    """Query helpers for workspace membership."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_membership(
        self,
        *,
        user_id: str,
        workspace_id: str,
    ) -> WorkspaceMembership | None:
        stmt = (
            select(WorkspaceMembership)
            .options(selectinload(WorkspaceMembership.workspace))
            .where(
                and_(
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.workspace_id == workspace_id,
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default_membership(self, *, user_id: str) -> WorkspaceMembership | None:
        stmt = (
            select(WorkspaceMembership)
            .options(selectinload(WorkspaceMembership.workspace))
            .where(
                and_(
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.is_default.is_(True),
                )
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[WorkspaceMembership]:
        stmt = (
            select(WorkspaceMembership)
            .options(selectinload(WorkspaceMembership.workspace))
            .where(WorkspaceMembership.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_workspace(self, workspace_id: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_membership(
        self,
        *,
        workspace_id: str,
        user_id: str,
        role: WorkspaceRole,
        permissions: Iterable[str] | None = None,
        is_default: bool = False,
    ) -> WorkspaceMembership:
        membership = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            is_default=is_default,
            permissions=list(permissions or ()),
        )
        self._session.add(membership)
        await self._session.flush()
        await self._session.refresh(membership, attribute_names=["workspace", "user"])
        return membership

__all__ = ["WorkspacesRepository"]
