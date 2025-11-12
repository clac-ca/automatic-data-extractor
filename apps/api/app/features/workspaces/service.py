"""Workspace domain services with role-based permissions."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.app.features.roles.models import (
    Permission,
    Principal,
    PrincipalType,
    Role,
    RoleAssignment,
    RolePermission,
    ScopeType,
)
from apps.api.app.features.roles.registry import PERMISSION_REGISTRY, SYSTEM_ROLES
from apps.api.app.features.roles.service import (
    AuthorizationError,
    assign_role,
    collect_permission_keys,
    ensure_user_principal,
    get_global_permissions_for_user,
    resolve_permission_ids,
    unassign_role,
)

from ..users.models import User
from ..users.repository import UsersRepository
from ..users.schemas import UserOut
from .models import Workspace, WorkspaceMembership

if TYPE_CHECKING:
    from apps.api.app.features.roles.schemas import RoleCreate, RoleUpdate
from .repository import WorkspacesRepository
from .schemas import (
    WorkspaceDefaultSelectionOut,
    WorkspaceMemberOut,
    WorkspaceMemberRolesUpdate,
    WorkspaceOut,
)

_GOVERNOR_PERMISSIONS = frozenset(
    {
        "Workspace.Roles.ReadWrite",
        "Workspace.Members.ReadWrite",
        "Workspace.Settings.ReadWrite",
    }
)

logger = logging.getLogger(__name__)

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


@dataclass(frozen=True)
class _MembershipRoleSummary:
    role_ids: frozenset[str]
    role_slugs: tuple[str, ...]
    permissions: tuple[str, ...]


_EMPTY_SUMMARY = _MembershipRoleSummary(frozenset(), (), ())


class WorkspacesService:
    """Resolve workspace membership for authenticated users."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._repo = WorkspacesRepository(session)
        self._users_repo = UsersRepository(session)

    async def get_workspace_profile(
        self,
        *,
        user: User,
        workspace_id: str | None,
    ) -> WorkspaceOut:
        """Return the workspace membership profile for ``user``."""

        global_permissions = await get_global_permissions_for_user(
            session=self._session, user=user
        )
        can_view_all_workspaces = bool(
            {"Workspaces.Read.All", "Workspaces.ReadWrite.All"} & global_permissions
        )

        if workspace_id is not None:
            if can_view_all_workspaces:
                workspace = await self._repo.get_workspace(workspace_id)
                if workspace is None:
                    raise HTTPException(
                        status.HTTP_404_NOT_FOUND, detail="Workspace not found"
                    )
                return self.build_global_admin_profile(workspace)

            membership = await self.resolve_membership(
                user=user, workspace_id=workspace_id
            )
            summaries = await self._summaries_for_workspace(
                workspace_id, [membership]
            )
            summary = self._summary_for_membership(
                membership=membership, summaries=summaries
            )
            return self.build_profile(membership, summary=summary)

        if can_view_all_workspaces:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Workspace identifier required"
            )

        membership = await self._repo.get_default_membership(user_id=cast(str, user.id))
        if membership is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="No default workspace configured",
            )
        workspace_identifier = cast(str, membership.workspace_id)
        summaries = await self._summaries_for_workspace(
            workspace_identifier, [membership]
        )
        summary = self._summary_for_membership(
            membership=membership, summaries=summaries
        )
        return self.build_profile(membership, summary=summary)

    async def list_memberships(self, *, user: User) -> list[WorkspaceOut]:
        """Return all workspace profiles associated with ``user`` in a stable order."""

        global_permissions = await get_global_permissions_for_user(
            session=self._session, user=user
        )
        if {
            "Workspaces.Read.All",
            "Workspaces.ReadWrite.All",
        } & global_permissions:
            workspaces = await self._repo.list_all()
            profiles = [self.build_global_admin_profile(workspace) for workspace in workspaces]
            profiles.sort(key=lambda profile: profile.slug)
            return profiles

        user_id = cast(str, user.id)
        memberships = await self._repo.list_for_user(user_id)
        workspace_identifiers = list(
            dict.fromkeys(cast(str, membership.workspace_id) for membership in memberships)
        )
        summaries_by_workspace: dict[str, dict[str, _MembershipRoleSummary]] = {}
        for workspace_identifier in workspace_identifiers:
            relevant_memberships = [
                membership
                for membership in memberships
                if cast(str, membership.workspace_id) == workspace_identifier
            ]
            if relevant_memberships:
                summaries_by_workspace[workspace_identifier] = (
                    await self._summaries_for_workspace(
                        workspace_identifier, relevant_memberships
                    )
                )
            else:
                summaries_by_workspace[workspace_identifier] = {}

        profiles: list[WorkspaceOut] = []
        for membership in memberships:
            workspace_identifier = cast(str, membership.workspace_id)
            summary_map = summaries_by_workspace.get(workspace_identifier, {})
            summary = self._summary_for_membership(
                membership=membership, summaries=summary_map
            )
            profiles.append(self.build_profile(membership, summary=summary))
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
    ) -> WorkspaceOut:
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
            await self._sync_workspace_assignments(
                membership=membership,
                workspace_id=cast(str, workspace.id),
                desired_role_ids=[cast(str, owner_role.id)],
            )

        membership = await self._reload_membership(
            membership_id=cast(str, membership.id),
            workspace_id=cast(str, workspace.id),
        )

        summaries = await self._summaries_for_workspace(
            cast(str, workspace.id), [membership]
        )
        summary = self._summary_for_membership(
            membership=membership, summaries=summaries
        )

        return self.build_profile(membership, summary=summary)

    async def update_workspace(
        self,
        *,
        user: User,
        workspace_id: str,
        name: str | None = None,
        slug: str | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> WorkspaceOut:
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

        return await self.get_workspace_profile(user=user, workspace_id=workspace_id)

    async def delete_workspace(self, *, workspace_id: str) -> None:
        workspace_record = await self._ensure_workspace(workspace_id)
        await self._repo.delete_workspace(workspace_record)

    async def list_members(self, *, workspace_id: str) -> list[WorkspaceMemberOut]:
        memberships = await self._repo.list_members(workspace_id)
        summaries = await self._summaries_for_workspace(workspace_id, memberships)
        return [
            self.build_member(
                membership,
                summary=self._summary_for_membership(
                    membership=membership, summaries=summaries
                ),
            )
            for membership in memberships
        ]

    async def assign_member_roles(
        self,
        *,
        workspace_id: str,
        membership_id: str,
        payload: WorkspaceMemberRolesUpdate,
    ) -> WorkspaceMemberOut:
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

        await self._sync_workspace_assignments(
            membership=membership,
            workspace_id=workspace_id,
            desired_role_ids=[cast(str, role.id) for role in roles],
        )
        membership = await self._reload_membership(
            membership_id=cast(str, membership.id),
            workspace_id=workspace_id,
        )
        summaries = await self._summaries_for_workspace(workspace_id, [membership])
        summary = self._summary_for_membership(
            membership=membership, summaries=summaries
        )
        return self.build_member(membership, summary=summary)

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

        await self._remove_workspace_assignments(
            membership=membership, workspace_id=workspace_id
        )
        await self._repo.delete_membership(membership)

    async def set_default_workspace(
        self,
        *,
        workspace_id: str,
        user: User,
    ) -> WorkspaceDefaultSelectionOut:
        membership = await self._repo.get_membership(
            user_id=cast(str, user.id), workspace_id=workspace_id
        )
        if membership is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Workspace access denied")

        await self._repo.clear_default_for_user(user_id=cast(str, user.id))
        membership.is_default = True
        await self._session.flush()

        return WorkspaceDefaultSelectionOut(workspace_id=workspace_id, is_default=True)

    async def add_member(
        self,
        *,
        workspace_id: str,
        user_id: str,
        role_ids: Sequence[str] | None,
    ) -> WorkspaceMemberOut:
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

        await self._sync_workspace_assignments(
            membership=membership,
            workspace_id=workspace_id,
            desired_role_ids=[cast(str, role.id) for role in roles],
        )
        membership = await self._reload_membership(
            membership_id=cast(str, membership.id),
            workspace_id=workspace_id,
        )
        summaries = await self._summaries_for_workspace(workspace_id, [membership])
        summary = self._summary_for_membership(
            membership=membership, summaries=summaries
        )
        return self.build_member(membership, summary=summary)

    async def _ensure_slug_available(
        self, *, workspace_id: str, slug: str
    ) -> None:
        existing = await self._session.execute(
            select(Role.id).where(
                Role.scope_type == ScopeType.WORKSPACE,
                Role.scope_id == workspace_id,
                Role.slug == slug,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Role slug already exists for this workspace",
            )

        system_conflict = await self._session.execute(
            select(Role.id).where(
                Role.scope_type == ScopeType.WORKSPACE,
                Role.scope_id.is_(None),
                Role.slug == slug,
            )
        )
        if system_conflict.scalar_one_or_none() is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Role slug conflicts with a system role",
            )

    async def create_workspace_role(
        self,
        *,
        workspace_id: str,
        payload: RoleCreate,
        actor: User,
    ) -> Role:
        normalized_name = self._normalize_role_name(payload.name)
        slug_source = payload.slug or normalized_name
        normalized_slug = _slugify(slug_source)
        if not normalized_slug:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Role slug is required",
            )

        await self._ensure_slug_available(
            workspace_id=workspace_id, slug=normalized_slug
        )

        permission_keys = self._normalize_workspace_permission_keys(
            payload.permissions
        )

        role = Role(
            scope_type=ScopeType.WORKSPACE,
            scope_id=workspace_id,
            slug=normalized_slug,
            name=normalized_name,
            description=self._normalize_description(payload.description),
            built_in=False,
            editable=True,
            created_by=cast(str | None, getattr(actor, "id", None)),
            updated_by=cast(str | None, getattr(actor, "id", None)),
        )
        self._session.add(role)
        await self._session.flush([role])

        if permission_keys:
            permission_map = await resolve_permission_ids(self._session, permission_keys)
            self._session.add_all(
                [
                    RolePermission(
                        role_id=cast(str, role.id),
                        permission_id=permission_map[key],
                    )
                    for key in permission_keys
                ]
            )

        await self._session.flush()
        await self._session.refresh(role, attribute_names=["permissions"])
        return role

    async def update_workspace_role(
        self,
        *,
        workspace_id: str,
        role_id: str,
        payload: RoleUpdate,
        actor: User,
    ) -> Role:
        role = await self._load_workspace_role(role_id, workspace_id)
        if not role.editable or role.built_in:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="System roles cannot be edited",
            )

        role.name = self._normalize_role_name(payload.name)
        role.description = self._normalize_description(payload.description)
        role.updated_by = cast(str | None, getattr(actor, "id", None))

        permission_keys = set(
            self._normalize_workspace_permission_keys(payload.permissions)
        )
        current_map = {
            permission.permission.key: permission.permission_id
            for permission in role.permissions
            if permission.permission is not None
        }
        current = set(current_map)

        additions = sorted(permission_keys - current)
        removals = sorted(current - permission_keys)

        if additions:
            permission_map = await resolve_permission_ids(self._session, additions)
            self._session.add_all(
                [
                    RolePermission(
                        role_id=cast(str, role.id),
                        permission_id=permission_map[key],
                    )
                    for key in additions
                ]
            )

        if removals:
            removal_ids = [current_map[key] for key in removals if key in current_map]
            if removal_ids:
                await self._session.execute(
                    delete(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id.in_(removal_ids),
                    )
                )

        await self._session.flush()

        if not await self._workspace_has_governor(workspace_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace requires at least one governor with elevated permissions",
            )

        await self._session.refresh(role, attribute_names=["permissions"])
        return role

    async def delete_workspace_role(
        self, *, workspace_id: str, role_id: str
    ) -> None:
        role = await self._load_workspace_role(role_id, workspace_id)
        if not role.editable or role.built_in:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="System roles cannot be deleted",
            )

        assignment_exists = await self._session.execute(
            select(RoleAssignment.id).where(
                RoleAssignment.role_id == role.id,
                RoleAssignment.scope_type == ScopeType.WORKSPACE,
            )
        )
        if assignment_exists.first() is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Role is assigned to one or more members",
            )

        await self._session.delete(role)
        await self._session.flush()

        if not await self._workspace_has_governor(workspace_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace requires at least one governor with elevated permissions",
            )

    def _normalize_role_name(self, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Role name is required",
            )
        return candidate

    @staticmethod
    def _normalize_description(value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    def _normalize_workspace_permission_keys(
        self, permissions: Iterable[str]
    ) -> tuple[str, ...]:
        try:
            collected = collect_permission_keys(permissions)
        except AuthorizationError as exc:  # pragma: no cover - validated via tests
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        unique = tuple(dict.fromkeys(collected))
        for key in unique:
            definition = PERMISSION_REGISTRY.get(key)
            if definition is None or definition.scope != "workspace":
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Permission '{key}' must be workspace-scoped",
                )
        return unique

    async def _load_workspace_role(self, role_id: str, workspace_id: str) -> Role:
        role = await self._session.get(Role, role_id)
        if (
            role is None
            or role.scope_type != "workspace"
            or (role.scope_id not in (None, workspace_id))
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")

        await self._session.refresh(role, attribute_names=["permissions"])
        return role

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

    def build_profile(
        self,
        membership: WorkspaceMembership,
        *,
        summary: _MembershipRoleSummary = _EMPTY_SUMMARY,
    ) -> WorkspaceOut:
        workspace = membership.workspace
        if workspace is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workspace missing"
            )

        permissions = list(summary.permissions)
        role_slugs = list(summary.role_slugs)
        return WorkspaceOut(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            roles=role_slugs,
            permissions=permissions,
            is_default=bool(membership.is_default),
        )

    def build_global_admin_profile(self, workspace: Workspace) -> WorkspaceOut:
        """Return an owner-level profile used when a global admin inspects a workspace."""

        permissions = sorted(dict.fromkeys(_system_role_permissions("workspace-owner")))
        return WorkspaceOut(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            roles=["workspace-owner"],
            permissions=permissions,
            is_default=False,
        )

    def build_member(
        self,
        membership: WorkspaceMembership,
        *,
        summary: _MembershipRoleSummary = _EMPTY_SUMMARY,
    ) -> WorkspaceMemberOut:
        user = membership.user
        if user is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Member user missing"
            )

        permissions = list(summary.permissions)
        role_slugs = list(summary.role_slugs)
        return WorkspaceMemberOut(
            id=membership.id,
            workspace_id=membership.workspace_id,
            roles=role_slugs,
            permissions=permissions,
            is_default=bool(membership.is_default),
            user=UserOut.model_validate(user),
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
            Role.scope_type == ScopeType.WORKSPACE,
            Role.scope_id.is_(None),
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
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.id.in_(unique_ids))
        )
        result = await self._session.execute(stmt)
        roles = list(result.scalars().all())
        found_ids = {cast(str, role.id) for role in roles}
        missing = [role_id for role_id in unique_ids if role_id not in found_ids]
        if missing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")

        for role in roles:
            if role.scope_type != "workspace":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Only workspace roles can be assigned to memberships",
                )
            if role.scope_id is not None and role.scope_id != workspace_id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Role is not defined for this workspace",
                )

        return roles

    async def _summaries_for_workspace(
        self,
        workspace_id: str,
        memberships: Sequence[WorkspaceMembership],
    ) -> dict[str, _MembershipRoleSummary]:
        user_ids = [
            cast(str, membership.user_id)
            for membership in memberships
            if membership.user_id is not None
        ]
        if not user_ids:
            return {}

        unique_user_ids = list(dict.fromkeys(user_ids))
        buckets: dict[str, dict[str, set[str]]] = {
            user_id: {"role_ids": set(), "role_slugs": set(), "permissions": set()}
            for user_id in unique_user_ids
        }

        stmt = (
            select(
                Principal.user_id,
                RoleAssignment.role_id,
                Role.slug,
                Permission.key,
            )
            .select_from(RoleAssignment)
            .join(Principal, Principal.id == RoleAssignment.principal_id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .outerjoin(RolePermission, RolePermission.role_id == Role.id)
            .outerjoin(Permission, Permission.id == RolePermission.permission_id)
            .where(
                RoleAssignment.scope_type == ScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
                Principal.principal_type == PrincipalType.USER,
                Principal.user_id.in_(unique_user_ids),
            )
        )
        result = await self._session.execute(stmt)
        for user_id, role_id, slug, permission_key in result:
            if user_id is None:
                continue
            bucket = buckets.setdefault(
                user_id,
                {"role_ids": set(), "role_slugs": set(), "permissions": set()},
            )
            if role_id is not None:
                bucket["role_ids"].add(role_id)
            if slug:
                bucket["role_slugs"].add(slug)
            if permission_key:
                bucket["permissions"].add(permission_key)

        return {
            user_id: _MembershipRoleSummary(
                role_ids=frozenset(bucket["role_ids"]),
                role_slugs=tuple(sorted(bucket["role_slugs"])),
                permissions=tuple(sorted(bucket["permissions"])),
            )
            for user_id, bucket in buckets.items()
        }

    @staticmethod
    def _summary_for_membership(
        *,
        membership: WorkspaceMembership,
        summaries: Mapping[str, _MembershipRoleSummary],
    ) -> _MembershipRoleSummary:
        user_identifier = cast(str | None, membership.user_id)
        if not user_identifier:
            return _EMPTY_SUMMARY
        return summaries.get(user_identifier, _EMPTY_SUMMARY)

    async def _sync_workspace_assignments(
        self,
        *,
        membership: WorkspaceMembership,
        workspace_id: str,
        desired_role_ids: Sequence[str],
    ) -> None:
        user = membership.user
        if user is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Member user missing",
            )

        principal = getattr(user, "principal", None)
        if principal is None:
            principal = await ensure_user_principal(session=self._session, user=user)

        desired_ids = set(dict.fromkeys(desired_role_ids))
        current_stmt = (
            select(RoleAssignment.role_id)
            .where(
                RoleAssignment.principal_id == principal.id,
                RoleAssignment.scope_type == ScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
            )
        )
        current_result = await self._session.execute(current_stmt)
        current_ids = set(current_result.scalars().all())

        additions = sorted(desired_ids - current_ids)
        removals = sorted(current_ids - desired_ids)

        for role_id in additions:
            await assign_role(
                session=self._session,
                principal_id=cast(str, principal.id),
                role_id=role_id,
                scope_type=ScopeType.WORKSPACE,
                scope_id=workspace_id,
            )

        for role_id in removals:
            await unassign_role(
                session=self._session,
                principal_id=cast(str, principal.id),
                role_id=role_id,
                scope_type=ScopeType.WORKSPACE,
                scope_id=workspace_id,
            )

    async def _remove_workspace_assignments(
        self,
        *,
        membership: WorkspaceMembership,
        workspace_id: str,
    ) -> None:
        user = membership.user
        if user is None:
            return

        principal = getattr(user, "principal", None)
        if principal is None:
            principal = await ensure_user_principal(session=self._session, user=user)

        await self._session.execute(
            delete(RoleAssignment).where(
                RoleAssignment.principal_id == principal.id,
                RoleAssignment.scope_type == ScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
            )
        )

    async def _workspace_has_governor(
        self,
        workspace_id: str,
        *,
        ignore_membership_id: str | None = None,
    ) -> bool:
        memberships = await self._repo.list_members_for_update(workspace_id)
        summaries = await self._summaries_for_workspace(workspace_id, memberships)
        for membership in memberships:
            if ignore_membership_id is not None and membership.id == ignore_membership_id:
                continue
            summary = self._summary_for_membership(
                membership=membership, summaries=summaries
            )
            if self._has_governor_permissions(summary.permissions):
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
            permissions.extend(
                permission.permission.key
                for permission in role.permissions
                if permission.permission is not None
            )
        return set(permissions)

__all__ = ["WorkspacesService"]
