from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
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
class MeService:
    """Business logic for the `/me` feature."""

    session: AsyncSession
    rbac: RbacService

    async def get_profile(self, principal: AuthenticatedPrincipal) -> MeProfile:
        """Return the user profile for the current principal."""
        if principal.principal_type is PrincipalType.SERVICE_ACCOUNT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Service account principals cannot access /me.",
            )

        user = await self._get_user_or_404(principal.user_id)
        return self._to_me_profile(user)

    async def get_context(
        self,
        principal: AuthenticatedPrincipal,
        *,
        page: int,
        page_size: int,
        include_total: bool = True,
    ) -> MeContext:
        """Return a consolidated bootstrap/context payload for the SPA."""
        profile = await self.get_profile(principal)

        global_roles = sorted(
            await self.rbac.get_global_role_slugs(principal=principal)
        )
        global_permissions = sorted(
            await self.rbac.get_global_permissions(principal=principal)
        )

        workspaces_page = await self._get_workspaces_for_principal(
            principal=principal,
            page=page,
            page_size=page_size,
            include_total=include_total,
        )

        return MeContext(
            user=profile,
            global_roles=global_roles,
            global_permissions=global_permissions,
            workspaces=workspaces_page,
        )

    async def get_effective_permissions(
        self,
        principal: AuthenticatedPrincipal,
        *,
        workspace_id: UUID | None = None,
    ) -> EffectivePermissions:
        """Return the effective permission sets for the principal."""
        global_permissions = await self.rbac.get_global_permissions(
            principal=principal
        )

        workspace_permissions: Iterable[str] = []
        if workspace_id is not None:
            await self._ensure_workspace_exists(workspace_id)
            workspace_permissions = await self.rbac.get_workspace_permissions(
                principal=principal,
                workspace_id=workspace_id,
            )

        return EffectivePermissions(
            global_permissions=sorted(global_permissions),
            workspace_id=workspace_id,
            workspace_permissions=sorted(set(workspace_permissions)),
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

        if workspace_keys and payload.workspace_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "workspace_id is required when checking workspace-scoped permissions."
                ),
            )

        global_perms = await self.rbac.get_global_permissions(principal=principal)

        workspace_perms: Iterable[str] = []
        if payload.workspace_id is not None:
            await self._ensure_workspace_exists(payload.workspace_id)
            workspace_perms = await self.rbac.get_workspace_permissions(
                principal=principal,
                workspace_id=payload.workspace_id,
            )

        workspace_perms_set = set(workspace_perms)

        results: dict[str, bool] = {}
        for key in requested_keys:
            definition = PERMISSION_REGISTRY.get(key)
            if definition is None:
                results[key] = False
                continue

            if definition.scope_type == ScopeType.GLOBAL:
                results[key] = key in global_perms
            else:
                results[key] = key in workspace_perms_set

        return PermissionCheckResponse(results=results)

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

    async def _get_workspaces_for_principal(
        self,
        principal: AuthenticatedPrincipal,
        *,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> MeWorkspacePage:
        """Return a paged list of workspaces visible to the principal."""

        memberships_stmt = (
            select(WorkspaceMembership, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(WorkspaceMembership.user_id == principal.user_id)
            .order_by(Workspace.name.asc())
        )

        memberships_result = await self.session.execute(memberships_stmt)
        rows = memberships_result.all()

        if rows:
            return await self._build_membership_workspace_page(
                rows=rows,
                page=page,
                page_size=page_size,
                include_total=include_total,
            )

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
        workspace_ids = [row[0] for row in assignments_result.all() if row[0] is not None]

        if not workspace_ids:
            return MeWorkspacePage(
                items=[],
                page=page,
                page_size=page_size,
                total=0 if include_total else None,
                has_next=False,
                has_previous=False,
            )

        workspaces_stmt = (
            select(Workspace)
            .where(Workspace.id.in_(workspace_ids))
            .order_by(Workspace.name.asc())
        )

        total: int | None = None
        if include_total:
            count_stmt = select(func.count()).select_from(workspaces_stmt.subquery())
            total_result = await self.session.execute(count_stmt)
            total = int(total_result.scalar_one() or 0)

        offset = (page - 1) * page_size
        workspaces_stmt = workspaces_stmt.offset(offset).limit(page_size)

        workspaces_result = await self.session.execute(workspaces_stmt)
        workspaces: list[Workspace] = list(workspaces_result.scalars().all())

        summaries = [
            MeWorkspaceSummary(
                id=workspace.id,
                name=workspace.name,
                slug=getattr(workspace, "slug", None),
                is_default=False,
                joined_at=None,
            )
            for workspace in workspaces
        ]

        has_previous = page > 1
        has_next = (
            len(summaries) == page_size
            and (total is None or (offset + len(summaries)) < total)
        )

        return MeWorkspacePage(
            items=summaries,
            page=page,
            page_size=page_size,
            total=total,
            has_next=has_next,
            has_previous=has_previous,
        )

    async def _build_membership_workspace_page(
        self,
        *,
        rows,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> MeWorkspacePage:
        """Build workspace page from membership query rows."""

        memberships: list[WorkspaceMembership] = []
        workspaces: list[Workspace] = []
        for membership, workspace in rows:
            memberships.append(membership)
            workspaces.append(workspace)

        total: int | None = None
        if include_total:
            total = len(workspaces)

        offset = (page - 1) * page_size
        slice_items = workspaces[offset : offset + page_size]
        slice_memberships = memberships[offset : offset + page_size]

        default_id: UUID | None = None
        for membership in memberships:
            if membership.is_default:
                default_id = membership.workspace_id
                break

        summaries: list[MeWorkspaceSummary] = []
        for membership, workspace in zip(
            slice_memberships, slice_items, strict=True
        ):
            summaries.append(
                MeWorkspaceSummary(
                    id=workspace.id,
                    name=workspace.name,
                    slug=workspace.slug,
                    is_default=default_id is not None and workspace.id == default_id,
                    joined_at=membership.created_at,
                )
            )

        has_previous = page > 1
        has_next = (
            len(summaries) == page_size
            and (total is None or (offset + len(summaries)) < total)
        )

        return MeWorkspacePage(
            items=summaries,
            page=page,
            page_size=page_size,
            total=total,
            has_next=has_next,
            has_previous=has_previous,
        )

    @staticmethod
    def _to_me_profile(user: User) -> MeProfile:
        return MeProfile(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_service_account=user.is_service_account,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
