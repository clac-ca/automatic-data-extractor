"""Workspace persistence helpers."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import and_, delete, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from ade_api.models import (
    Configuration,
    Environment,
    File,
    FileComment,
    FileCommentMention,
    FileTag,
    FileVersion,
    Run,
    RunField,
    RunMetrics,
    RunTableColumn,
    UserRoleAssignment,
    Workspace,
    WorkspaceMembership,
)


class WorkspacesRepository:
    """Query helpers for workspace membership."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_membership(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMembership | None:
        stmt = (
            select(WorkspaceMembership)
            .options(
                selectinload(WorkspaceMembership.workspace),
                selectinload(WorkspaceMembership.user),
            )
            .where(
                and_(
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.workspace_id == workspace_id,
                )
            )
            .execution_options(populate_existing=True)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_membership_for_workspace(
        self, *, user_id: UUID, workspace_id: UUID
    ) -> WorkspaceMembership | None:
        stmt = (
            select(WorkspaceMembership)
            .options(
                selectinload(WorkspaceMembership.workspace),
                selectinload(WorkspaceMembership.user),
            )
            .where(
                and_(
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.workspace_id == workspace_id,
                )
            )
            .execution_options(populate_existing=True)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_default_membership(self, *, user_id: UUID) -> WorkspaceMembership | None:
        stmt = (
            select(WorkspaceMembership)
            .options(
                selectinload(WorkspaceMembership.workspace),
                selectinload(WorkspaceMembership.user),
            )
            .where(
                and_(
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.is_default == true(),
                )
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def list_for_user(self, user_id: UUID) -> list[WorkspaceMembership]:
        stmt = (
            select(WorkspaceMembership)
            .options(
                selectinload(WorkspaceMembership.workspace),
                selectinload(WorkspaceMembership.user),
            )
            .where(WorkspaceMembership.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def list_members(self, workspace_id: UUID) -> list[WorkspaceMembership]:
        stmt = (
            select(WorkspaceMembership)
            .options(
                selectinload(WorkspaceMembership.workspace),
                selectinload(WorkspaceMembership.user),
            )
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .execution_options(populate_existing=True)
        )
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def list_members_for_update(self, workspace_id: UUID) -> list[WorkspaceMembership]:
        stmt = (
            select(WorkspaceMembership)
            .options(
                selectinload(WorkspaceMembership.workspace),
                selectinload(WorkspaceMembership.user),
            )
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_workspace_by_slug(self, slug: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.slug == slug)
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def list_all(self) -> list[Workspace]:
        stmt = select(Workspace).order_by(Workspace.slug)
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def create_workspace(
        self,
        *,
        name: str,
        slug: str,
        settings: Mapping[str, object] | None = None,
    ) -> Workspace:
        workspace = Workspace(name=name, slug=slug, settings=dict(settings or {}))
        self._session.add(workspace)
        try:
            self._session.flush()
        except IntegrityError:  # pragma: no cover - surfaced as HTTP 409
            raise
        self._session.refresh(workspace)
        return workspace

    def update_workspace(
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
            self._session.flush()
        except IntegrityError:  # pragma: no cover - surfaced as HTTP 409
            raise
        self._session.refresh(workspace)
        return workspace

    def delete_workspace(self, workspace: Workspace) -> None:
        workspace_id = workspace.id
        run_ids = select(Run.id).where(Run.workspace_id == workspace_id)
        file_ids = select(File.id).where(File.workspace_id == workspace_id)
        file_version_ids = select(FileVersion.id).where(FileVersion.file_id.in_(file_ids))

        # Delete in dependency order to satisfy FK constraints across workspace data.
        self._session.execute(
            update(FileVersion)
            .where(FileVersion.id.in_(file_version_ids))
            .values(run_id=None)
        )
        self._session.execute(
            delete(RunTableColumn).where(RunTableColumn.run_id.in_(run_ids))
        )
        self._session.execute(delete(RunField).where(RunField.run_id.in_(run_ids)))
        self._session.execute(delete(RunMetrics).where(RunMetrics.run_id.in_(run_ids)))
        self._session.execute(delete(Run).where(Run.workspace_id == workspace_id))
        self._session.execute(
            delete(Environment).where(Environment.workspace_id == workspace_id)
        )

        self._session.execute(
            delete(FileCommentMention).where(
                FileCommentMention.comment_id.in_(
                    select(FileComment.id).where(FileComment.file_id.in_(file_ids))
                )
            )
        )
        self._session.execute(delete(FileComment).where(FileComment.file_id.in_(file_ids)))
        self._session.execute(delete(FileTag).where(FileTag.file_id.in_(file_ids)))
        self._session.execute(delete(FileVersion).where(FileVersion.file_id.in_(file_ids)))
        self._session.execute(delete(File).where(File.workspace_id == workspace_id))

        self._session.execute(
            delete(Configuration).where(Configuration.workspace_id == workspace_id)
        )
        self._session.execute(
            delete(UserRoleAssignment).where(UserRoleAssignment.workspace_id == workspace_id)
        )
        self._session.execute(
            delete(WorkspaceMembership).where(WorkspaceMembership.workspace_id == workspace_id)
        )
        self._session.delete(workspace)
        self._session.flush()

    def create_membership(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        is_default: bool = False,
    ) -> WorkspaceMembership:
        membership = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_id,
            is_default=is_default,
        )
        self._session.add(membership)
        self._session.flush()
        self._session.refresh(
            membership,
            attribute_names=["workspace", "user"],
        )
        return membership

    def delete_membership(self, membership: WorkspaceMembership) -> None:
        self._session.delete(membership)
        self._session.flush()

    def clear_default_for_user(self, *, user_id: UUID) -> None:
        stmt = (
            update(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user_id)
            .values(is_default=False)
        )
        self._session.execute(stmt)


__all__ = ["WorkspacesRepository"]
