"""Service layer for workspace resolution."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..users.models import User, UserRole
from ..users.repository import UsersRepository
from ..users.schemas import UserProfile
from app.features.roles.registry import SYSTEM_ROLES

from .models import Workspace, WorkspaceMembership, WorkspaceRole
from .repository import WorkspacesRepository
from .schemas import (
    WorkspaceDefaultSelection,
    WorkspaceMember,
    WorkspaceProfile,
)


def _system_role_permissions(slug: str) -> tuple[str, ...]:
    for definition in SYSTEM_ROLES:
        if definition.slug == slug:
            return definition.permissions
    return ()


ROLE_PERMISSION_DEFAULTS: dict[WorkspaceRole, tuple[str, ...]] = {
    WorkspaceRole.MEMBER: _system_role_permissions("workspace-member"),
    WorkspaceRole.OWNER: _system_role_permissions("workspace-owner"),
}


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    """Return a URL-safe slug derived from ``value``."""

    candidate = _SLUG_PATTERN.sub("-", value.lower()).strip("-")
    candidate = re.sub(r"-{2,}", "-", candidate)
    return candidate


class WorkspacesService:
    """Resolve workspace membership for authenticated users."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._repo = WorkspacesRepository(session)
        self._users_repo = UsersRepository(session)

    async def resolve_selection(
        self,
        *,
        user: User,
        workspace_id: str | None,
    ) -> WorkspaceProfile:
        """Return the workspace membership profile for ``user``."""

        if workspace_id is not None:
            if user.role is UserRole.ADMIN:
                workspace = await self._repo.get_workspace(workspace_id)
                if workspace is None:
                    raise HTTPException(
                        status.HTTP_404_NOT_FOUND, detail="Workspace not found"
                    )
                profile = self.build_global_admin_profile(workspace)
                return profile

            membership = await self.resolve_membership(
                user=user, workspace_id=workspace_id
            )
            return self.build_profile(membership)

        if user.role is UserRole.ADMIN:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Workspace identifier required"
            )

        membership = await self._repo.get_default_membership(user_id=cast(str, user.id))
        if membership is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="No default workspace configured",
            )
        return self.build_profile(membership)

    async def list_memberships(self, *, user: User) -> list[WorkspaceProfile]:
        """Return all workspace profiles associated with ``user`` in a stable order."""

        if user.role is UserRole.ADMIN:
            workspaces = await self._repo.list_all()
            profiles = [self.build_global_admin_profile(workspace) for workspace in workspaces]
            profiles.sort(key=lambda profile: profile.slug)
            return profiles

        user_id = cast(str, user.id)
        memberships = await self._repo.list_for_user(user_id)
        profiles = [self.build_profile(membership) for membership in memberships]
        profiles.sort(key=lambda profile: (not profile.is_default, profile.slug))
        return profiles

    async def create_workspace(
        self,
        *,
        user: User,
        name: str,
        slug: str | None = None,
        owner_user_id: str | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> WorkspaceProfile:
        normalized_name = name.strip()
        if not normalized_name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name required")

        slug_source = slug.strip() if slug is not None else normalized_name
        normalized_slug = _slugify(slug_source)
        if not normalized_slug:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slug")

        existing = await self._repo.get_workspace_by_slug(normalized_slug)
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Workspace slug already in use")

        try:
            workspace = await self._repo.create_workspace(
                name=normalized_name,
                slug=normalized_slug,
                settings=settings,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive double check
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Workspace slug already in use"
            ) from exc

        owner_id = owner_user_id or cast(str, user.id)
        owner = await self._users_repo.get_by_id(owner_id)
        if owner is None or not owner.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Owner not found")

        membership = await self._repo.create_membership(
            workspace_id=cast(str, workspace.id),
            user_id=cast(str, owner.id),
            role=WorkspaceRole.OWNER,
        )
        return self.build_profile(membership)

    async def update_workspace(
        self,
        *,
        user: User,
        workspace_id: str,
        name: str | None = None,
        slug: str | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> WorkspaceProfile:
        workspace_record = await self._ensure_workspace(workspace_id)

        updated_name: str | None = None
        if name is not None:
            updated_name = name.strip()
            if not updated_name:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name required")

        updated_slug: str | None = None
        if slug is not None:
            slug_source = slug.strip()
            if not slug_source:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slug")
            candidate = _slugify(slug_source)
            if not candidate:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slug")
            if candidate != workspace_record.slug:
                existing = await self._repo.get_workspace_by_slug(candidate)
                if existing is not None and existing.id != workspace_record.id:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT, detail="Workspace slug already in use"
                    )
                updated_slug = candidate

        try:
            await self._repo.update_workspace(
                workspace_record,
                name=updated_name,
                slug=updated_slug,
                settings=settings,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive double check
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Workspace slug already in use"
            ) from exc

        return await self.resolve_selection(user=user, workspace_id=workspace_id)

    async def delete_workspace(self, *, workspace_id: str) -> None:
        workspace_record = await self._ensure_workspace(workspace_id)
        await self._repo.delete_workspace(workspace_record)

    async def list_members(self, *, workspace_id: str) -> list[WorkspaceMember]:
        memberships = await self._repo.list_members(workspace_id)
        return [self.build_member(membership) for membership in memberships]

    async def update_member_role(
        self,
        *,
        workspace_id: str,
        membership_id: str,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        membership = await self._repo.get_membership_for_workspace(
            membership_id=membership_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Membership not found")

        if membership.role is WorkspaceRole.OWNER and role is not WorkspaceRole.OWNER:
            owner_count = await self._repo.count_members_with_role(
                workspace_id=workspace_id, role=WorkspaceRole.OWNER
            )
            if owner_count <= 1:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Workspace requires at least one owner",
                )

        if membership.role is role:
            return self.build_member(membership)

        updated = await self._repo.update_membership_role(membership, role)
        return self.build_member(updated)

    async def remove_member(
        self,
        *,
        workspace_id: str,
        membership_id: str,
    ) -> None:
        membership = await self._repo.get_membership_for_workspace(
            membership_id=membership_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Membership not found")

        if membership.role is WorkspaceRole.OWNER:
            owner_count = await self._repo.count_members_with_role(
                workspace_id=workspace_id, role=WorkspaceRole.OWNER
            )
            if owner_count <= 1:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Workspace requires at least one owner",
                )

        await self._repo.delete_membership(membership)

    async def set_default_workspace(
        self,
        *,
        workspace_id: str,
        user: User,
    ) -> WorkspaceDefaultSelection:
        membership = await self._repo.get_membership(
            user_id=cast(str, user.id), workspace_id=workspace_id
        )
        if membership is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Workspace access denied")

        await self._repo.clear_default_for_user(user_id=cast(str, user.id))
        membership.is_default = True
        await self._session.flush()

        return WorkspaceDefaultSelection(workspace_id=workspace_id, is_default=True)

    async def add_member(
        self,
        *,
        workspace_id: str,
        user_id: str,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        """Add ``user_id`` to ``workspace_id`` with the supplied ``role``."""

        existing = await self._repo.get_membership(
            user_id=user_id, workspace_id=workspace_id
        )
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="User already a workspace member",
            )

        user = await self._users_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

        membership = await self._repo.create_membership(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
        return self.build_member(membership)

    async def resolve_membership(
        self, *, user: User, workspace_id: str
    ) -> WorkspaceMembership:
        """Return the ``WorkspaceMembership`` link for ``user`` and ``workspace_id``."""

        return await self._resolve_membership(
            user_id=cast(str, user.id), workspace_id=workspace_id
        )

    async def _resolve_membership(
        self, *, user_id: str, workspace_id: str
    ) -> WorkspaceMembership:
        membership = await self._repo.get_membership(
            user_id=user_id, workspace_id=workspace_id
        )
        if membership is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Workspace access denied")
        return membership

    def build_profile(self, membership: WorkspaceMembership) -> WorkspaceProfile:
        workspace = membership.workspace
        if workspace is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workspace missing"
            )

        permissions = self._permissions_for_role(membership.role)
        return WorkspaceProfile(
            workspace_id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            role=membership.role,
            permissions=permissions,
            is_default=bool(membership.is_default),
        )

    def build_global_admin_profile(self, workspace: Workspace) -> WorkspaceProfile:
        """Return an owner-level profile used when a global admin inspects a workspace."""

        permissions = self._permissions_for_role(WorkspaceRole.OWNER)
        return WorkspaceProfile(
            workspace_id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            role=WorkspaceRole.OWNER,
            permissions=permissions,
            is_default=False,
        )

    def build_member(self, membership: WorkspaceMembership) -> WorkspaceMember:
        user = membership.user
        if user is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Member user missing"
            )

        permissions = self._permissions_for_role(membership.role)
        return WorkspaceMember(
            workspace_membership_id=membership.id,
            workspace_id=membership.workspace_id,
            role=membership.role,
            permissions=permissions,
            is_default=bool(membership.is_default),
            user=UserProfile.model_validate(user),
        )

    async def _ensure_workspace(self, workspace_id: str) -> Workspace:
        workspace = await self._repo.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        return workspace

    @staticmethod
    def _permissions_for_role(role: WorkspaceRole) -> list[str]:
        permissions = ROLE_PERMISSION_DEFAULTS.get(role, ())
        return sorted(dict.fromkeys(permissions))


__all__ = [
    "ROLE_PERMISSION_DEFAULTS",
    "WorkspacesService",
]
