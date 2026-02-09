from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ade_api.common.time import utc_now
from ade_api.core.auth.principal import AuthenticatedPrincipal, AuthVia, PrincipalType
from ade_api.core.rbac.registry import PERMISSION_REGISTRY, SYSTEM_ROLE_BY_SLUG
from ade_api.core.rbac.service_interface import RbacService
from ade_api.core.rbac.types import ScopeType
from ade_db.models import User, UserRoleAssignment, Workspace, WorkspaceMembership

from .schemas import (
    EffectivePermissions,
    MeContext,
    MeProfile,
    MeProfileUpdateRequest,
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

    session: Session
    rbac: RbacService

    def get_profile(self, principal: AuthenticatedPrincipal) -> MeProfile:
        """Return the user profile for the current principal."""

        user, roles, permissions, access = self._load_principal_state(principal)
        return self._to_me_profile(
            user=user,
            roles=roles,
            permissions=permissions,
            preferred_workspace_id=access.default_workspace_id,
        )

    def get_context(
        self,
        principal: AuthenticatedPrincipal,
    ) -> MeContext:
        """Return a consolidated bootstrap/context payload for the SPA."""

        user, roles, permissions, access = self._load_principal_state(principal)

        workspaces = self._build_workspace_list(access=access)

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
            workspaces=workspaces,
        )

    def update_profile(
        self,
        principal: AuthenticatedPrincipal,
        payload: MeProfileUpdateRequest,
    ) -> MeProfile:
        """Update editable fields on the caller profile."""

        user, roles, permissions, access = self._load_principal_state(principal)

        if "display_name" not in payload.model_fields_set:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No editable profile fields were provided.",
            )

        user.display_name = payload.display_name
        self.session.flush()

        return self._to_me_profile(
            user=user,
            roles=roles,
            permissions=permissions,
            preferred_workspace_id=access.default_workspace_id,
        )

    def get_effective_permissions(
        self,
        principal: AuthenticatedPrincipal,
    ) -> EffectivePermissions:
        """Return the full effective permission sets for the principal."""

        global_permissions = sorted(self.rbac.get_global_permissions(principal=principal))

        access = self._resolve_workspace_access(principal)
        workspace_permissions: dict[str, list[str]] = {}
        for workspace in access.workspaces:
            permissions = self.rbac.get_workspace_permissions(
                principal=principal,
                workspace_id=workspace.id,
            )
            workspace_permissions[str(workspace.id)] = sorted(set(permissions))

        return EffectivePermissions(
            global_=global_permissions,
            workspaces=workspace_permissions,
        )

    def check_permissions(
        self,
        principal: AuthenticatedPrincipal,
        payload: PermissionCheckRequest,
    ) -> PermissionCheckResponse:
        """Check whether the principal has each requested permission key."""

        if not payload.permissions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=("workspace_id is required when checking workspace-scoped permissions."),
            )

        global_perms = self.rbac.get_global_permissions(principal=principal)

        workspace_perms: set[str] = set()
        if workspace_id is not None:
            self._ensure_workspace_exists(workspace_id)
            workspace_perms = self.rbac.get_workspace_permissions(
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

    def _load_principal_state(
        self, principal: AuthenticatedPrincipal
    ) -> tuple[User, list[str], list[str], WorkspaceAccess]:
        """Resolve the persisted user, role/permission sets, and workspace access."""

        if principal.principal_type is PrincipalType.SERVICE_ACCOUNT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Service account principals cannot access /me.",
            )

        if principal.auth_via is AuthVia.DEV:
            return self._load_dev_principal_state(principal)

        user = self._get_user_or_404(principal.user_id)
        roles = sorted(self.rbac.get_global_role_slugs(principal=principal))
        permissions = sorted(self.rbac.get_global_permissions(principal=principal))
        access = self._resolve_workspace_access(principal)
        return user, roles, permissions, access

    def _load_dev_principal_state(
        self,
        principal: AuthenticatedPrincipal,
    ) -> tuple[User, list[str], list[str], WorkspaceAccess]:
        now = utc_now()
        email = principal.email or "developer@example.com"
        user = User(
            email=email,
            hashed_password="",
            display_name="Developer",
            is_service_account=False,
            is_active=True,
            is_verified=True,
            last_login_at=now,
            failed_login_count=0,
            locked_until=None,
        )
        user.id = principal.user_id
        user.created_at = now
        user.updated_at = now

        role = SYSTEM_ROLE_BY_SLUG["global-admin"]
        access = self._resolve_dev_workspace_access(principal)
        return user, [role.slug], sorted(role.permissions), access

    def _resolve_dev_workspace_access(
        self,
        principal: AuthenticatedPrincipal,
    ) -> WorkspaceAccess:
        """Resolve workspace visibility for auth-disabled development principals."""

        access = self._resolve_workspace_access(principal)
        if access.workspaces:
            return access

        workspaces_stmt = select(Workspace)
        workspaces_result = self.session.execute(workspaces_stmt)
        workspaces = sorted(
            workspaces_result.scalars().all(),
            key=lambda workspace: workspace.name.lower(),
        )
        default_workspace_id = access.default_workspace_id
        if default_workspace_id is None and workspaces:
            default_workspace_id = workspaces[0].id

        return WorkspaceAccess(
            workspaces=workspaces,
            memberships=access.memberships,
            default_workspace_id=default_workspace_id,
        )

    def _get_user_or_404(self, user_id: UUID) -> User:
        user = self.session.get(User, user_id)
        if user is None or not getattr(user, "is_active", True):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User record not found.",
            )
        return user

    def _ensure_workspace_exists(self, workspace_id: UUID) -> None:
        workspace = self.session.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found.",
            )

    def _resolve_workspace_access(self, principal: AuthenticatedPrincipal) -> WorkspaceAccess:
        """Return all workspaces visible to the principal (memberships + assignments)."""

        membership_stmt = (
            select(WorkspaceMembership, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(WorkspaceMembership.user_id == principal.user_id)
        )
        membership_result = self.session.execute(membership_stmt)

        memberships: dict[UUID, WorkspaceMembership] = {}
        workspace_map: dict[UUID, Workspace] = {}
        default_workspace_id: UUID | None = None

        for membership, workspace in membership_result.all():
            memberships[membership.workspace_id] = membership
            workspace_map[workspace.id] = workspace
            if membership.is_default and default_workspace_id is None:
                default_workspace_id = membership.workspace_id

        assignments_stmt = (
            select(UserRoleAssignment.workspace_id)
            .where(
                UserRoleAssignment.user_id == principal.user_id,
                UserRoleAssignment.workspace_id.is_not(None),
            )
            .distinct()
        )
        assignments_result = self.session.execute(assignments_stmt)
        assigned_ids = {row[0] for row in assignments_result.all() if row[0] is not None}
        missing_ids = [ws_id for ws_id in assigned_ids if ws_id not in workspace_map]

        if missing_ids:
            workspaces_stmt = select(Workspace).where(Workspace.id.in_(missing_ids))
            workspaces_result = self.session.execute(workspaces_stmt)
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

    def _build_workspace_list(
        self,
        *,
        access: WorkspaceAccess,
    ) -> list[MeWorkspaceSummary]:
        """Build workspace summaries for the bootstrap payload."""

        summaries: list[MeWorkspaceSummary] = []
        for workspace in access.workspaces:
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
        return summaries

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
