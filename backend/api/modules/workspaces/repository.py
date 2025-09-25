"""Workspace persistence helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.exc import IntegrityError
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

    async def get_membership_by_id(
        self, membership_id: str
    ) -> WorkspaceMembership | None:
        stmt = (
            select(WorkspaceMembership)
            .options(
                selectinload(WorkspaceMembership.workspace),
                selectinload(WorkspaceMembership.user),
            )
            .where(WorkspaceMembership.id == membership_id)
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

    async def list_members(self, workspace_id: str) -> list[WorkspaceMembership]:
        stmt = (
            select(WorkspaceMembership)
            .options(
                selectinload(WorkspaceMembership.workspace),
                selectinload(WorkspaceMembership.user),
            )
            .where(WorkspaceMembership.workspace_id == workspace_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_workspace(self, workspace_id: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_workspace_by_slug(self, slug: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Workspace]:
        stmt = select(Workspace).order_by(Workspace.slug)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_workspace(
        self,
        *,
        name: str,
        slug: str,
        settings: Mapping[str, object] | None = None,
    ) -> Workspace:
        workspace = Workspace(name=name, slug=slug, settings=dict(settings or {}))
        self._session.add(workspace)
        try:
            await self._session.flush()
        except IntegrityError:  # pragma: no cover - surfaced as HTTP 409
            raise
        await self._session.refresh(workspace)
        return workspace

    async def update_workspace(
        self,
        workspace: Workspace,
        *,
        name: str | None = None,
        slug: str | None = None,
        settings: Mapping[str, object] | None = None,
    ) -> Workspace:
        if name is not None:
            workspace.name = name
        if slug is not None:
            workspace.slug = slug
        if settings is not None:
            workspace.settings = dict(settings)
        try:
            await self._session.flush()
        except IntegrityError:  # pragma: no cover - surfaced as HTTP 409
            raise
        await self._session.refresh(workspace)
        return workspace

    async def delete_workspace(self, workspace: Workspace) -> None:
        await self._session.execute(
            delete(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace.id
            )
        )
        await self._session.delete(workspace)
        await self._session.flush()

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

    async def update_membership_role(
        self, membership: WorkspaceMembership, role: WorkspaceRole
    ) -> WorkspaceMembership:
        membership.role = role
        await self._session.flush()
        await self._session.refresh(membership, attribute_names=["workspace", "user"])
        return membership

    async def delete_membership(self, membership: WorkspaceMembership) -> None:
        await self._session.delete(membership)
        await self._session.flush()

    async def count_members_with_role(
        self, *, workspace_id: str, role: WorkspaceRole
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(WorkspaceMembership)
            .where(
                and_(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.role == role,
                )
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def clear_default_for_user(self, *, user_id: str) -> None:
        stmt = (
            update(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user_id)
            .values(is_default=False)
        )
        await self._session.execute(stmt)


__all__ = ["WorkspacesRepository"]
