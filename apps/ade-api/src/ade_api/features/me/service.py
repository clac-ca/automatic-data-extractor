from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.auth.principal import AuthenticatedPrincipal, PrincipalType
from ade_api.core.models import User, Workspace, WorkspaceMembership
from ade_api.core.models.rbac import ScopeType, UserRoleAssignment
from ade_api.core.rbac.registry import PERMISSION_REGISTRY
from ade_api.core.rbac.service_interface import RbacService

from .schemas import (
    EffectivePermissions,
    MeContext,
    MeProfile,
    MeWorkspacePage,
    MeWorkspaceSummary,
    PermissionCheckRequest,
    PermissionCheckResponse,
)


@dataclass
class WorkspaceAccess:
    """Normalized view of workspaces visible to the principal."""

    workspaces: list[Workspace]
    memberships: dict[UUID, WorkspaceMembership]
    default_workspace_id: UUID | None


@dataclass
class MeService:
    """Business logic for the `/me` feature."""

    session: AsyncSession
    rbac: RbacService

    async def get_profile(self, principal: AuthenticatedPrincipal) -> MeProfile:
        """Return the user profile for the current principal."""

        user, roles, permissions, access = await self._load_principal_state(principal)
        return self._to_me_profile(
            user=user,
            roles=roles,
            permissions=permissions,
            preferred_workspace_id=access.default_workspace_id,
        )

    async def get_context(
        self,
        principal: AuthenticatedPrincipal,
        *,
        page: int,
        page_size: int,
        include_total: bool = True,
    ) -> MeContext:
        """Return a consolidated bootstrap/context payload for the SPA."""

        user, roles, permissions, access = await self._load_principal_state(principal)

        workspaces_page = self._build_workspace_page(
            access=access,
            page=page,
            page_size=page_size,
            include_total=include_total,
        )

        profile = self._to_me_profile(
            user=user,
            roles=roles,
            permissions=permissions,
            preferred_workspace_id=access.default_workspace_id,
        )

        return MeContext(
            user=profile,
            roles=roles,
            permissions=permissions,
            workspaces=workspaces_page,
        )

    async def get_effective_permissions(
        self,
        principal: AuthenticatedPrincipal,
    ) -> EffectivePermissions:
        """Return the full effective permission sets for the principal."""

        global_permissions = sorted(
            await self.rbac.get_global_permissions(principal=principal)
        )

        access = await self._resolve_workspace_access(principal)
        workspace_permissions: dict[str, list[str]] = {}
        for workspace in access.workspaces:
            permissions = await self.rbac.get_workspace_permissions(
                principal=principal,
                workspace_id=workspace.id,
            )
            workspace_permissions[str(workspace.id)] = sorted(set(permissions))

        return EffectivePermissions(
            global_=global_permissions,
            workspaces=workspace_permissions,
        )

    async def check_permissions(
        self,
        principal: AuthenticatedPrincipal,
        payload: PermissionCheckRequest,
    ) -> PermissionCheckResponse:
        """Check whether the principal has each requested permission key."""

        if not payload.permissions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="permissions must contain at least one permission key.",
            )

        requested_keys = list(dict.fromkeys(p.strip() for p in payload.permissions))

        workspace_keys: list[str] = []
        for key in requested_keys:
            definition = PERMISSION_REGISTRY.get(key)
            if definition is None:
                continue
            if definition.scope_type != ScopeType.GLOBAL:
                workspace_keys.append(key)

        workspace_id: UUID | None = (
            UUID(str(payload.workspace_id)) if payload.workspace_id is not None else None
        )

        if workspace_keys and workspace_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "workspace_id is required when checking workspace-scoped permissions."
                ),
            )

        global_perms = await self.rbac.get_global_permissions(principal=principal)

        workspace_perms: set[str] = set()
        if workspace_id is not None:
            await self._ensure_workspace_exists(workspace_id)
            workspace_perms = await self.rbac.get_workspace_permissions(
                principal=principal,
                workspace_id=workspace_id,
            )

        results: dict[str, bool] = {}
        for key in requested_keys:
            definition = PERMISSION_REGISTRY.get(key)
            if definition is None:
                results[key] = False
                continue

            if definition.scope_type == ScopeType.GLOBAL:
                results[key] = key in global_perms
            else:
                results[key] = key in workspace_perms

        return PermissionCheckResponse(results=results)

    async def _load_principal_state(
        self, principal: AuthenticatedPrincipal
    ) -> tuple[User, list[str], list[str], WorkspaceAccess]:
        """Resolve the persisted user, role/permission sets, and workspace access."""

        if principal.principal_type is PrincipalType.SERVICE_ACCOUNT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Service account principals cannot access /me.",
            )

        user = await self._get_user_or_404(principal.user_id)
        roles = sorted(await self.rbac.get_global_role_slugs(principal=principal))
        permissions = sorted(await self.rbac.get_global_permissions(principal=principal))
        access = await self._resolve_workspace_access(principal)
        return user, roles, permissions, access

    async def _get_user_or_404(self, user_id: UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None or not getattr(user, "is_active", True):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User record not found.",
            )
        return user

    async def _ensure_workspace_exists(self, workspace_id: UUID) -> None:
        workspace = await self.session.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found.",
            )

    async def _resolve_workspace_access(
        self, principal: AuthenticatedPrincipal
    ) -> WorkspaceAccess:
        """Return all workspaces visible to the principal (memberships + assignments)."""

        membership_stmt = (
            select(WorkspaceMembership, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(WorkspaceMembership.user_id == principal.user_id)
        )
        membership_result = await self.session.execute(membership_stmt)

        memberships: dict[UUID, WorkspaceMembership] = {}
        workspace_map: dict[UUID, Workspace] = {}
        default_workspace_id: UUID | None = None

        for membership, workspace in membership_result.all():
            memberships[membership.workspace_id] = membership
            workspace_map[workspace.id] = workspace
            if membership.is_default and default_workspace_id is None:
                default_workspace_id = membership.workspace_id

        assignments_stmt = (
            select(UserRoleAssignment.scope_id)
            .where(
                UserRoleAssignment.user_id == principal.user_id,
                UserRoleAssignment.scope_type == ScopeType.WORKSPACE,
                UserRoleAssignment.scope_id.is_not(None),
            )
            .distinct()
        )
        assignments_result = await self.session.execute(assignments_stmt)
        assigned_ids = {
            row[0] for row in assignments_result.all() if row[0] is not None
        }
        missing_ids = [ws_id for ws_id in assigned_ids if ws_id not in workspace_map]

        if missing_ids:
            workspaces_stmt = select(Workspace).where(Workspace.id.in_(missing_ids))
            workspaces_result = await self.session.execute(workspaces_stmt)
            for workspace in workspaces_result.scalars().all():
                workspace_map[workspace.id] = workspace

        ordered = sorted(
            workspace_map.values(),
            key=lambda workspace: workspace.name.lower(),
        )

        return WorkspaceAccess(
            workspaces=list(ordered),
            memberships=memberships,
            default_workspace_id=default_workspace_id,
        )

    def _build_workspace_page(
        self,
        *,
        access: WorkspaceAccess,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> MeWorkspacePage:
        """Build workspace pagination metadata and summaries."""

        total = len(access.workspaces) if include_total else None
        offset = max(0, (page - 1) * page_size)
        slice_items = access.workspaces[offset : offset + page_size]

        summaries: list[MeWorkspaceSummary] = []
        for workspace in slice_items:
            membership = access.memberships.get(workspace.id)
            summaries.append(
                MeWorkspaceSummary(
                    id=workspace.id,
                    name=workspace.name,
                    slug=workspace.slug,
                    is_default=(
                        access.default_workspace_id is not None
                        and workspace.id == access.default_workspace_id
                    ),
                    joined_at=membership.created_at if membership else None,
                )
            )

        has_previous = page > 1
        has_next = (offset + len(slice_items)) < len(access.workspaces)

        return MeWorkspacePage(
            items=summaries,
            page=page,
            page_size=page_size,
            total=total,
            has_next=has_next,
            has_previous=has_previous,
        )

    @staticmethod
    def _to_me_profile(
        *,
        user: User,
        roles: Sequence[str],
        permissions: Sequence[str],
        preferred_workspace_id: UUID | None,
    ) -> MeProfile:
        return MeProfile(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_service_account=user.is_service_account,
            preferred_workspace_id=preferred_workspace_id,
            roles=list(roles),
            permissions=list(permissions),
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
