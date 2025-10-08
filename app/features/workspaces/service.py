"""Workspace domain services with role-based permissions."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.roles.models import Role
from app.features.roles.registry import SYSTEM_ROLES
from ..users.models import User, UserRole
from ..users.repository import UsersRepository
from ..users.schemas import UserProfile
from .models import Workspace, WorkspaceMembership
from .repository import WorkspacesRepository
from .schemas import (
    WorkspaceDefaultSelection,
    WorkspaceMember,
    WorkspaceMemberRolesUpdate,
    WorkspaceProfile,
)


_GOVERNOR_PERMISSIONS = frozenset(
    {
        "Workspace.Roles.ReadWrite",
        "Workspace.Members.ReadWrite",
        "Workspace.Settings.ReadWrite",
    }
)

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    """Return a URL-safe slug derived from ``value``."""

    candidate = _SLUG_PATTERN.sub("-", value.lower()).strip("-")
    candidate = re.sub(r"-{2,}", "-", candidate)
    return candidate


def _system_role_permissions(slug: str) -> tuple[str, ...]:
    for definition in SYSTEM_ROLES:
        if definition.slug == slug:
            return definition.permissions
    return ()


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
                return self.build_global_admin_profile(workspace)

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
        )

        owner_role = await self._get_system_workspace_role("workspace-owner")
        if owner_role is not None:
            await self._repo.set_membership_roles(
                membership_id=cast(str, membership.id),
                role_ids=[cast(str, owner_role.id)],
            )

        membership = await self._reload_membership(
            membership_id=cast(str, membership.id),
            workspace_id=cast(str, workspace.id),
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

    async def assign_member_roles(
        self,
        *,
        workspace_id: str,
        membership_id: str,
        payload: WorkspaceMemberRolesUpdate,
    ) -> WorkspaceMember:
        membership = await self._repo.get_membership_for_workspace(
            membership_id=membership_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Membership not found")

        roles = await self._resolve_roles_for_assignment(
            workspace_id=workspace_id,
            role_ids=payload.role_ids,
        )

        if not await self._workspace_has_governor(
            workspace_id, ignore_membership_id=cast(str, membership.id)
        ) and not self._has_governor_permissions(
            self._permissions_from_roles(roles)
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace requires at least one governor with elevated permissions",
            )

        await self._repo.set_membership_roles(
            membership_id=cast(str, membership.id),
            role_ids=[cast(str, role.id) for role in roles],
        )
        membership = await self._reload_membership(
            membership_id=cast(str, membership.id),
            workspace_id=workspace_id,
        )
        return self.build_member(membership)

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

        if not await self._workspace_has_governor(
            workspace_id, ignore_membership_id=cast(str, membership.id)
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace requires at least one governor with elevated permissions",
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
        role_ids: Sequence[str] | None,
    ) -> WorkspaceMember:
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
        )

        roles = await self._resolve_roles_for_assignment(
            workspace_id=workspace_id,
            role_ids=list(role_ids or []),
        )
        if not roles:
            member_role = await self._get_system_workspace_role("workspace-member")
            if member_role is not None:
                roles = [member_role]

        await self._repo.set_membership_roles(
            membership_id=cast(str, membership.id),
            role_ids=[cast(str, role.id) for role in roles],
        )
        membership = await self._reload_membership(
            membership_id=cast(str, membership.id),
            workspace_id=workspace_id,
        )
        return self.build_member(membership)

    async def list_workspace_roles(self, workspace_id: str) -> list[Role]:
        return await self._repo.list_workspace_roles(workspace_id)

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

        permissions = self._permissions_for_membership(membership)
        role_slugs = self._slugs_for_membership(membership)
        return WorkspaceProfile(
            workspace_id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            roles=role_slugs,
            permissions=permissions,
            is_default=bool(membership.is_default),
        )

    def build_global_admin_profile(self, workspace: Workspace) -> WorkspaceProfile:
        """Return an owner-level profile used when a global admin inspects a workspace."""

        permissions = sorted(dict.fromkeys(_system_role_permissions("workspace-owner")))
        return WorkspaceProfile(
            workspace_id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            roles=["workspace-owner"],
            permissions=permissions,
            is_default=False,
        )

    def build_member(self, membership: WorkspaceMembership) -> WorkspaceMember:
        user = membership.user
        if user is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Member user missing"
            )

        permissions = self._permissions_for_membership(membership)
        role_slugs = self._slugs_for_membership(membership)
        return WorkspaceMember(
            workspace_membership_id=membership.id,
            workspace_id=membership.workspace_id,
            roles=role_slugs,
            permissions=permissions,
            is_default=bool(membership.is_default),
            user=UserProfile.model_validate(user),
        )

    async def _ensure_workspace(self, workspace_id: str) -> Workspace:
        workspace = await self._repo.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        return workspace

    async def _reload_membership(
        self, *, membership_id: str, workspace_id: str
    ) -> WorkspaceMembership:
        refreshed = await self._repo.get_membership_for_workspace(
            membership_id=membership_id,
            workspace_id=workspace_id,
        )
        if refreshed is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Workspace membership not found after update",
            )
        return refreshed

    async def _get_system_workspace_role(self, slug: str) -> Role | None:
        stmt = select(Role).where(
            Role.slug == slug,
            Role.scope == "workspace",
            Role.workspace_id.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _resolve_roles_for_assignment(
        self,
        *,
        workspace_id: str,
        role_ids: Sequence[str],
    ) -> list[Role]:
        if not role_ids:
            return []

        unique_ids = list(dict.fromkeys(role_ids))
        stmt = select(Role).where(Role.id.in_(unique_ids))
        result = await self._session.execute(stmt)
        roles = list(result.scalars().all())
        found_ids = {cast(str, role.id) for role in roles}
        missing = [role_id for role_id in unique_ids if role_id not in found_ids]
        if missing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")

        for role in roles:
            if role.scope != "workspace":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Only workspace roles can be assigned to memberships",
                )
            if role.workspace_id is not None and role.workspace_id != workspace_id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Role is not defined for this workspace",
                )

        return roles

    async def _workspace_has_governor(
        self,
        workspace_id: str,
        *,
        ignore_membership_id: str | None = None,
    ) -> bool:
        memberships = await self._repo.list_members(workspace_id)
        for membership in memberships:
            if ignore_membership_id is not None and membership.id == ignore_membership_id:
                continue
            if self._has_governor_permissions(
                self._permissions_for_membership(membership)
            ):
                return True
        return False

    @staticmethod
    def _has_governor_permissions(permissions: Iterable[str]) -> bool:
        permission_set = set(permissions)
        return all(key in permission_set for key in _GOVERNOR_PERMISSIONS)

    @staticmethod
    def _permissions_from_roles(roles: Sequence[Role]) -> set[str]:
        permissions: list[str] = []
        for role in roles:
            permissions.extend(permission.permission_key for permission in role.permissions)
        return set(permissions)

    def _permissions_for_membership(self, membership: WorkspaceMembership) -> list[str]:
        keys: list[str] = []
        for assignment in membership.membership_roles:
            role = assignment.role
            if role is None:
                continue
            keys.extend(permission.permission_key for permission in role.permissions)
        if not keys:
            return []
        return sorted(dict.fromkeys(keys))

    def _slugs_for_membership(self, membership: WorkspaceMembership) -> list[str]:
        slugs = [
            assignment.role.slug
            for assignment in membership.membership_roles
            if assignment.role is not None
        ]
        return sorted(dict.fromkeys(slugs))


__all__ = ["WorkspacesService"]
