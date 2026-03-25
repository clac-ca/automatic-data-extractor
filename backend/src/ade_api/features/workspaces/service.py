"""Workspace domain services aligned with the new RBAC model."""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ade_api.common.cursor_listing import ResolvedCursorSort, paginate_sequence_cursor
from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.logging import log_context
from ade_api.common.search import matches_tokens, parse_q
from ade_api.core.rbac.registry import role_allows_scope
from ade_api.features.rbac import (
    RbacService,
    RoleConflictError,
    RoleImmutableError,
    RoleNotFoundError,
    RoleValidationError,
    ScopeMismatchError,
    ScopeType,
)
from ade_api.settings import Settings
from ade_db.models import (
    AssignmentScopeType,
    Group,
    GroupMembership,
    PrincipalType,
    Role,
    RoleAssignment,
    RolePermission,
    User,
    UserRoleAssignment,
    Workspace,
    WorkspaceMembership,
)

from ..users.repository import UsersRepository
from .effective_members import (
    EffectiveWorkspaceMember,
    EffectiveWorkspaceMembersResolver,
    role_grants_workspace_access,
)
from .filters import (
    evaluate_member_filters,
    evaluate_workspace_filters,
    parse_workspace_filters,
    parse_workspace_member_filters,
)
from .repository import WorkspacesRepository
from .schemas import (
    WorkspaceDefaultSelectionOut,
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceMemberPage,
    WorkspaceMemberUpdate,
    WorkspaceOut,
    WorkspacePage,
)
from .settings import apply_processing_paused, read_processing_paused

if TYPE_CHECKING:
    from ade_api.features.rbac.schemas import RoleCreate, RoleUpdate

logger = logging.getLogger(__name__)

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_GLOBAL_WORKSPACE_PERMS = {"workspaces.manage_all", "workspaces.read_all"}
_WORKSPACE_OWNER_SLUG = "workspace-owner"
_WORKSPACE_MEMBER_SLUG = "workspace-member"


def _slugify(value: str) -> str:
    candidate = _SLUG_PATTERN.sub("-", value.lower()).strip("-")
    candidate = re.sub(r"-{2,}", "-", candidate)
    return candidate


class WorkspacesService:
    """Resolve workspace membership and manage workspace-scoped roles."""

    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = WorkspacesRepository(session)
        self._users_repo = UsersRepository(session)
        self._rbac = RbacService(session=session)
        self._effective_members = EffectiveWorkspaceMembersResolver(
            session=session,
            settings=settings,
        )

    # ------------------------------------------------------------------
    # Workspace profiles
    # ------------------------------------------------------------------
    @staticmethod
    def _processing_paused(workspace: Workspace | None) -> bool:
        if workspace is None:
            return False
        return read_processing_paused(workspace.settings)

    def get_workspace_profile(
        self,
        *,
        user: User,
        workspace_id: UUID | None,
    ) -> WorkspaceOut:
        """Return the workspace membership profile for ``user``."""

        user_id = user.id
        logger.debug(
            "workspace.profile.start",
            extra=log_context(user_id=user_id, workspace_id=workspace_id),
        )

        global_permissions = self._rbac.get_global_permissions_for_user(user=user)
        is_global_admin = bool(_GLOBAL_WORKSPACE_PERMS & global_permissions)

        if workspace_id is not None:
            workspace = self._repo.get_workspace(workspace_id)
            if workspace is None:
                logger.warning(
                    "workspace.profile.workspace_not_found",
                    extra=log_context(user_id=user_id, workspace_id=workspace_id),
                )
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="Workspace not found",
                )

            if is_global_admin:
                permissions = self._rbac.get_workspace_permissions_for_user(
                    user=user, workspace_id=workspace_id
                )
                role_slugs = self._workspace_role_slugs_for_user(
                    user_id=user_id,
                    workspace_id=workspace_id,
                )
                membership = self._repo.get_membership_for_workspace(
                    user_id=user_id,
                    workspace_id=workspace_id,
                )
                profile = WorkspaceOut(
                    id=workspace.id,
                    name=workspace.name,
                    slug=workspace.slug,
                    roles=sorted(role_slugs),
                    permissions=sorted(permissions),
                    is_default=membership.is_default if membership else False,
                    processing_paused=self._processing_paused(workspace),
                )
                logger.info(
                    "workspace.profile.global_admin",
                    extra=log_context(
                        user_id=user_id,
                        workspace_id=workspace_id,
                        roles=profile.roles,
                        permissions=len(profile.permissions),
                    ),
                )
                return profile

            permissions = self._rbac.get_workspace_permissions_for_user(
                user=user,
                workspace_id=workspace_id,
            )
            if not permissions:
                logger.warning(
                    "workspace.profile.access_not_found",
                    extra=log_context(user_id=user_id, workspace_id=workspace_id),
                )
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="Workspace not found",
                )
            membership = self._repo.get_membership_for_workspace(
                user_id=user_id,
                workspace_id=workspace_id,
            )
            role_slugs = self._workspace_role_slugs_for_user(
                user_id=user_id,
                workspace_id=workspace_id,
            )
            profile = WorkspaceOut(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                roles=sorted(role_slugs),
                permissions=sorted(permissions),
                is_default=membership.is_default if membership else False,
                processing_paused=self._processing_paused(workspace),
            )
            logger.info(
                "workspace.profile.success",
                extra=log_context(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    roles=profile.roles,
                    permissions=len(profile.permissions),
                    is_default=profile.is_default,
                ),
            )
            return profile

        if is_global_admin:
            logger.warning(
                "workspace.profile.missing_workspace_id",
                extra=log_context(user_id=user_id),
            )
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Workspace identifier required",
            )

        membership = self._repo.get_default_membership(user_id=user_id)
        if membership is not None:
            workspace_identifier = membership.workspace_id
            permissions = self._rbac.get_workspace_permissions_for_user(
                user=user,
                workspace_id=workspace_identifier,
            )
            if permissions:
                role_slugs = self._workspace_role_slugs_for_user(
                    user_id=user_id,
                    workspace_id=workspace_identifier,
                )
                profile = WorkspaceOut(
                    id=membership.workspace_id,
                    name=membership.workspace.name if membership.workspace else "",
                    slug=membership.workspace.slug if membership.workspace else "",
                    roles=sorted(role_slugs),
                    permissions=sorted(permissions),
                    is_default=membership.is_default,
                    processing_paused=self._processing_paused(membership.workspace),
                )
                logger.info(
                    "workspace.profile.default_success",
                    extra=log_context(
                        user_id=user_id,
                        workspace_id=workspace_identifier,
                        roles=profile.roles,
                        permissions=len(profile.permissions),
                        is_default=profile.is_default,
                    ),
                )
                return profile

        memberships = self.list_memberships(
            user=user,
            global_permissions=global_permissions,
        )
        if not memberships:
            logger.warning(
                "workspace.profile.no_accessible_workspace",
                extra=log_context(user_id=user_id),
            )
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="No workspace access found",
            )
        fallback = memberships[0]
        logger.info(
            "workspace.profile.default_fallback",
            extra=log_context(
                user_id=user_id,
                workspace_id=fallback.id,
                roles=fallback.roles,
                permissions=len(fallback.permissions),
            ),
        )
        return fallback

    def list_memberships(
        self,
        *,
        user: User,
        global_permissions: frozenset[str] | None = None,
    ) -> list[WorkspaceOut]:
        """Return workspace profiles associated with ``user``."""

        user_id = user.id
        logger.debug(
            "workspace.memberships.list.start",
            extra=log_context(user_id=user_id),
        )

        if user.is_service_account:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Service accounts cannot access workspaces",
            )

        if global_permissions is None:
            global_permissions = self._rbac.get_global_permissions_for_user(user=user)
        is_global_admin = bool(_GLOBAL_WORKSPACE_PERMS & global_permissions)

        profiles: list[WorkspaceOut] = []
        if is_global_admin:
            workspaces = self._repo.list_all()
            for workspace in workspaces:
                permissions = self._rbac.get_workspace_permissions_for_user(
                    user=user, workspace_id=workspace.id
                )
                role_slugs = self._workspace_role_slugs_for_user(
                    user_id=user_id,
                    workspace_id=workspace.id,
                )
                membership = self._repo.get_membership_for_workspace(
                    user_id=user_id,
                    workspace_id=workspace.id,
                )
                profiles.append(
                    WorkspaceOut(
                        id=workspace.id,
                        name=workspace.name,
                        slug=workspace.slug,
                        roles=sorted(role_slugs),
                        permissions=sorted(permissions),
                        is_default=membership.is_default if membership else False,
                        processing_paused=self._processing_paused(workspace),
                    )
                )
            profiles.sort(key=lambda profile: profile.slug)
        else:
            memberships = self._repo.list_for_user(user_id=user_id)
            membership_by_workspace = {
                membership.workspace_id: membership for membership in memberships
            }
            workspace_ids = self._workspace_ids_with_access(user=user)
            workspace_ids.update(membership_by_workspace.keys())
            for workspace_id in workspace_ids:
                workspace = self._repo.get_workspace(workspace_id)
                if workspace is None:
                    continue
                permissions = self._rbac.get_workspace_permissions_for_user(
                    user=user,
                    workspace_id=workspace_id,
                )
                if not permissions:
                    continue
                membership = membership_by_workspace.get(workspace_id)
                role_slugs = self._workspace_role_slugs_for_user(
                    user_id=user_id,
                    workspace_id=workspace_id,
                )
                profiles.append(
                    WorkspaceOut(
                        id=workspace.id,
                        name=workspace.name,
                        slug=workspace.slug,
                        roles=sorted(role_slugs),
                        permissions=sorted(permissions),
                        is_default=membership.is_default if membership else False,
                        processing_paused=self._processing_paused(workspace),
                    )
                )
            profiles.sort(key=lambda profile: profile.slug)

        logger.info(
            "workspace.memberships.list.success",
            extra=log_context(user_id=user_id, count=len(profiles)),
        )
        return profiles

    def list_workspaces(
        self,
        *,
        user: User,
        resolved_sort: ResolvedCursorSort[WorkspaceOut],
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        limit: int,
        cursor: str | None,
        include_total: bool,
        global_permissions: frozenset[str] | None = None,
    ) -> WorkspacePage:
        memberships = self.list_memberships(
            user=user,
            global_permissions=global_permissions,
        )
        parsed_filters = parse_workspace_filters(filters)
        filtered = [
            item
            for item in memberships
            if evaluate_workspace_filters(
                item,
                parsed_filters,
                join_operator=join_operator,
                q=q,
            )
        ]
        page_result = paginate_sequence_cursor(
            filtered,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )
        return WorkspacePage(
            items=page_result.items, meta=page_result.meta, facets=page_result.facets
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create_workspace(
        self,
        *,
        user: User,
        name: str,
        slug: str | None,
        owner_user_id: UUID | None = None,
        settings: Mapping[str, object] | None = None,
        processing_paused: bool | None = None,
    ) -> WorkspaceOut:
        slug_value = _slugify(slug or name)
        if not slug_value:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Workspace slug is required",
            )
        self._ensure_slug_available(slug_value)

        owner_id = owner_user_id or user.id
        owner = self._users_repo.get_by_id(owner_id)
        if owner is None or not owner.is_active:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Owner not found",
            )

        logger.debug(
            "workspace.create.start",
            extra=log_context(slug=slug_value, owner_id=owner_id),
        )

        settings_payload = (
            apply_processing_paused(settings, processing_paused)
            if settings is not None or processing_paused is not None
            else None
        )
        try:
            workspace = self._repo.create_workspace(
                name=name.strip(),
                slug=slug_value,
                settings=settings_payload,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive double check
            logger.warning(
                "workspace.create.conflict",
                extra=log_context(slug=slug_value),
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace slug already exists",
            ) from exc

        existing_default = self._repo.get_default_membership(user_id=owner_id)
        membership = self._repo.create_membership(
            workspace_id=workspace.id,
            user_id=owner_id,
            is_default=existing_default is None,
        )

        self._assign_default_roles(
            user_id=owner_id,
            workspace_id=workspace.id,
            role_slugs=[_WORKSPACE_OWNER_SLUG],
        )

        permissions = self._rbac.get_workspace_permissions_for_user(
            user=owner,
            workspace_id=workspace.id,
        )
        profile = WorkspaceOut(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            roles=[_WORKSPACE_OWNER_SLUG],
            permissions=sorted(permissions),
            is_default=membership.is_default,
            processing_paused=self._processing_paused(workspace),
        )
        logger.info(
            "workspace.create.success",
            extra=log_context(
                workspace_id=workspace.id,
                slug=workspace.slug,
                owner_id=str(owner_id),
            ),
        )
        return profile

    def update_workspace(
        self,
        *,
        user: User,
        workspace_id: UUID,
        name: str | None,
        slug: str | None,
        settings: Mapping[str, object] | None = None,
        processing_paused: bool | None = None,
    ) -> WorkspaceOut:
        workspace = self._ensure_workspace(workspace_id)
        slug_value = _slugify(slug) if slug else None
        if slug_value:
            self._ensure_slug_available(slug_value, current_id=workspace.id)

        settings_payload = None
        if settings is not None or processing_paused is not None:
            if settings is not None:
                base_settings = dict(settings)
            else:
                base_settings = dict(workspace.settings or {})
            settings_payload = apply_processing_paused(base_settings, processing_paused)

        try:
            workspace = self._repo.update_workspace(
                workspace,
                name=name.strip() if name else None,
                slug=slug_value,
                settings=settings_payload,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive double check
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace slug already exists",
            ) from exc

        permissions = self._rbac.get_workspace_permissions_for_user(
            user=user,
            workspace_id=workspace_id,
        )
        membership = self._repo.get_membership_for_workspace(
            user_id=user.id,
            workspace_id=workspace_id,
        )
        role_slugs = self._workspace_role_slugs_for_user(
            user_id=user.id,
            workspace_id=workspace_id,
        )
        profile = WorkspaceOut(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            roles=sorted(role_slugs),
            permissions=sorted(permissions),
            is_default=membership.is_default if membership else False,
            processing_paused=self._processing_paused(workspace),
        )
        return profile

    def delete_workspace(self, *, workspace_id: UUID) -> None:
        workspace = self._ensure_workspace(workspace_id)
        self._repo.delete_workspace(workspace)
        storage_errors = self._delete_workspace_storage(workspace_id)
        if storage_errors:
            logger.warning(
                "workspace.delete.storage_incomplete",
                extra=log_context(
                    workspace_id=workspace_id,
                    error_count=len(storage_errors),
                    error_paths=[str(path) for path, _exc in storage_errors],
                ),
            )
        logger.info(
            "workspace.delete.success",
            extra=log_context(workspace_id=workspace_id),
        )

    def set_default_workspace(
        self,
        *,
        workspace_id: UUID,
        user: User,
    ) -> WorkspaceDefaultSelectionOut:
        membership = self._repo.get_membership_for_workspace(
            user_id=user.id,
            workspace_id=workspace_id,
        )
        if membership is None:
            permissions = self._rbac.get_workspace_permissions_for_user(
                user=user,
                workspace_id=workspace_id,
            )
            if not permissions:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="Workspace not found",
                )
            membership = self._repo.create_membership(
                workspace_id=workspace_id,
                user_id=user.id,
                is_default=False,
            )

        self._session.execute(
            update(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user.id)
            .values(is_default=False)
        )
        membership.is_default = True
        self._session.flush()
        return WorkspaceDefaultSelectionOut(
            workspace_id=workspace_id,
            is_default=True,
        )

    # ------------------------------------------------------------------
    # Workspace members
    # ------------------------------------------------------------------
    def list_workspace_members(
        self,
        *,
        workspace_id: UUID,
        resolved_sort: ResolvedCursorSort[WorkspaceMemberOut],
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        limit: int,
        cursor: str | None,
        include_total: bool,
    ) -> WorkspaceMemberPage:
        self._ensure_workspace(workspace_id)
        parsed_filters = parse_workspace_member_filters(filters)
        members = [
            self._serialize_effective_member(member)
            for member in self._effective_members.list_members(workspace_id=workspace_id)
        ]
        members = [
            member
            for member in members
            if evaluate_member_filters(member, parsed_filters, join_operator=join_operator)
        ]
        if q:
            tokens = parse_q(q).tokens
            members = [
                member
                for member in members
                if matches_tokens(
                    tokens,
                    [
                        member.user.display_name,
                        member.user.email,
                    ],
                )
            ]
        page_result = paginate_sequence_cursor(
            members,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )
        return WorkspaceMemberPage(
            items=page_result.items, meta=page_result.meta, facets=page_result.facets
        )

    def add_workspace_member(
        self,
        *,
        workspace_id: UUID,
        payload: WorkspaceMemberCreate,
    ) -> WorkspaceMemberOut:
        self._ensure_workspace(workspace_id)

        if not payload.role_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="role_ids must include at least one role",
            )

        self._validate_member_target_user(user_id=payload.user_id)
        self._validate_member_role_ids(role_ids=payload.role_ids)
        self._assign_roles_to_member(
            user_id=payload.user_id,
            workspace_id=workspace_id,
            role_ids=payload.role_ids,
        )

        membership = self._repo.get_membership_for_workspace(
            user_id=payload.user_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            self._repo.create_membership(
                workspace_id=workspace_id,
                user_id=payload.user_id,
                is_default=False,
            )

        return self._serialize_effective_member(
            self._load_effective_member(workspace_id=workspace_id, user_id=payload.user_id)
        )

    def update_workspace_member_roles(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        payload: WorkspaceMemberUpdate,
    ) -> WorkspaceMemberOut:
        self._ensure_workspace(workspace_id)

        if not payload.role_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="role_ids must include at least one role",
            )

        self._validate_member_target_user(user_id=user_id)
        self._validate_member_role_ids(role_ids=payload.role_ids)

        membership = self._repo.get_membership_for_workspace(
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            self._repo.create_membership(
                workspace_id=workspace_id,
                user_id=user_id,
                is_default=False,
            )

        self._replace_member_roles(
            user_id=user_id,
            workspace_id=workspace_id,
            role_ids=list(payload.role_ids),
        )

        return self._serialize_effective_member(
            self._load_effective_member(workspace_id=workspace_id, user_id=user_id)
        )

    def remove_workspace_member(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> None:
        self._ensure_workspace(workspace_id)

        direct_assignments = self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        direct_principal_assignments = self._get_direct_user_principal_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        effective_member = self._effective_members.member_by_user_id(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not direct_assignments and not direct_principal_assignments and effective_member is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )

        for assignment in direct_assignments:
            self._rbac.delete_assignment(
                assignment_id=assignment.id,
                workspace_id=workspace_id,
            )
        legacy_role_ids = {assignment.role_id for assignment in direct_assignments}
        for assignment in direct_principal_assignments:
            if assignment.role_id in legacy_role_ids:
                continue
            self._rbac.delete_principal_assignment(assignment_id=assignment.id)
        self._delete_membership_if_exists(
            workspace_id=workspace_id,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Role definitions scoped for workspace use
    # ------------------------------------------------------------------
    def create_workspace_role(
        self,
        *,
        workspace_id: UUID,
        payload: RoleCreate,
        actor: User,
    ) -> Role:
        self._ensure_workspace(workspace_id)
        try:
            return self._rbac.create_role(
                name=payload.name,
                slug=payload.slug,
                description=payload.description,
                permissions=payload.permissions,
                actor=actor,
            )
        except RoleConflictError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except RoleValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

    def update_workspace_role(
        self,
        *,
        workspace_id: UUID,
        role_id: UUID,
        payload: RoleUpdate,
        actor: User,
    ) -> Role:
        self._ensure_workspace(workspace_id)
        existing_role = self._rbac.get_role(role_id)
        if existing_role is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )
        existing_permissions = [
            assignment.permission.key
            for assignment in existing_role.permissions
            if assignment.permission is not None
        ]
        try:
            role = self._rbac.update_role(
                role_id=role_id,
                name=payload.name or existing_role.name,
                description=(
                    payload.description
                    if payload.description is not None
                    else existing_role.description
                ),
                permissions=payload.permissions or existing_permissions,
                actor=actor,
            )
        except RoleImmutableError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RoleValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except RoleNotFoundError as exc:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        return role

    def delete_workspace_role(
        self,
        *,
        workspace_id: UUID,
        role_id: UUID,
    ) -> None:
        self._ensure_workspace(workspace_id)
        assignments = self._session.execute(
            select(UserRoleAssignment.id).where(
                UserRoleAssignment.role_id == role_id,
            )
        )
        if assignments.scalar_one_or_none() is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Role is assigned to one or more members",
            )
        try:
            self._rbac.delete_role(role_id=role_id)
        except RoleImmutableError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RoleNotFoundError as exc:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_slug_available(self, slug: str, current_id: UUID | None = None) -> None:
        existing = self._repo.get_workspace_by_slug(slug)
        if existing is not None and str(existing.id) != str(current_id or ""):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace slug already exists",
            )

    def _ensure_workspace(self, workspace_id: UUID) -> Workspace:
        workspace = self._repo.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        return workspace

    def _delete_workspace_storage(self, workspace_id: UUID) -> list[tuple[Path, Exception]]:
        paths = self._workspace_storage_paths(workspace_id)
        if not paths:
            return []
        return self._remove_storage_paths(paths)

    def _workspace_storage_paths(self, workspace_id: UUID) -> list[Path]:
        roots = [
            self._settings.workspaces_dir,
            self._settings.configs_dir,
            self._settings.documents_dir,
            self._settings.runs_dir,
            self._settings.venvs_dir,
        ]
        candidates = [Path(root) / str(workspace_id) for root in roots]
        seen: set[Path] = set()
        paths: list[Path] = []
        for candidate in candidates:
            resolved = candidate.expanduser().resolve()
            if resolved not in seen:
                seen.add(resolved)
                paths.append(resolved)
        paths.sort(key=lambda path: len(path.parents), reverse=True)
        return paths

    @staticmethod
    def _remove_storage_paths(paths: Sequence[Path]) -> list[tuple[Path, Exception]]:
        errors: list[tuple[Path, Exception]] = []
        for path in paths:
            try:
                if not path.exists() and not path.is_symlink():
                    continue
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            except Exception as exc:  # noqa: BLE001
                errors.append((path, exc))
        return errors

    def _get_workspace_assignments(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID | None = None,
        include_inactive: bool = True,
    ) -> list[UserRoleAssignment]:
        stmt = (
            select(UserRoleAssignment)
            .options(
                selectinload(UserRoleAssignment.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission),
                selectinload(UserRoleAssignment.user),
            )
            .where(
                UserRoleAssignment.workspace_id == workspace_id,
            )
        )
        if user_id:
            stmt = stmt.where(UserRoleAssignment.user_id == user_id)
        if not include_inactive:
            stmt = stmt.join(User, UserRoleAssignment.user).where(User.is_active == true())
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def _get_direct_user_principal_assignments(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> list[RoleAssignment]:
        stmt = select(RoleAssignment).where(
            RoleAssignment.principal_type == PrincipalType.USER,
            RoleAssignment.principal_id == user_id,
            RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
            RoleAssignment.scope_id == workspace_id,
        )
        result = self._session.execute(stmt)
        return list(result.scalars().all())

    def _serialize_effective_member(
        self,
        member: EffectiveWorkspaceMember,
    ) -> WorkspaceMemberOut:
        sources = sorted(
            member.source_map.values(),
            key=lambda source: (
                0 if source.principal_type == PrincipalType.USER else 1,
                (
                    source.principal_display_name
                    or source.principal_email
                    or source.principal_slug
                    or str(source.principal_id)
                ).lower(),
                str(source.principal_id),
            ),
        )
        role_pairs = sorted(
            member.role_map.items(),
            key=lambda item: (item[1].lower(), str(item[0])),
        )
        if member.has_direct_access and member.has_indirect_access:
            access_mode = "mixed"
        elif member.has_direct_access:
            access_mode = "direct"
        else:
            access_mode = "indirect"

        return WorkspaceMemberOut(
            user_id=member.user.id,
            role_ids=[role_id for role_id, _role_slug in role_pairs],
            role_slugs=[role_slug for _role_id, role_slug in role_pairs],
            created_at=member.created_at or member.user.created_at,
            user={
                "id": member.user.id,
                "email": member.user.email,
                "display_name": member.user.display_name,
            },
            access_mode=access_mode,
            is_directly_managed=member.has_direct_access,
            sources=[
                {
                    "principal_type": source.principal_type,
                    "principal_id": source.principal_id,
                    "principal_display_name": source.principal_display_name,
                    "principal_email": source.principal_email,
                    "principal_slug": source.principal_slug,
                    "role_ids": [
                        role_id
                        for role_id, _role_slug in sorted(
                            source.role_map.items(),
                            key=lambda item: (item[1].lower(), str(item[0])),
                        )
                    ],
                    "role_slugs": [
                        role_slug
                        for _role_id, role_slug in sorted(
                            source.role_map.items(),
                            key=lambda item: (item[1].lower(), str(item[0])),
                        )
                    ],
                    "created_at": source.created_at or member.user.created_at,
                }
                for source in sources
            ],
        )

    def _delete_membership_if_exists(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> None:
        membership = self._repo.get_membership_for_workspace(
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if membership is not None:
            self._repo.delete_membership(membership)

    def _workspace_role_slugs_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> list[str]:
        role_slugs: set[str] = set()

        legacy_stmt = (
            select(Role.slug)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.workspace_id == workspace_id,
            )
        )
        role_slugs.update(self._session.execute(legacy_stmt).scalars().all())

        direct_stmt = (
            select(Role.slug)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .where(
                RoleAssignment.principal_type == PrincipalType.USER,
                RoleAssignment.principal_id == user_id,
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
            )
        )
        role_slugs.update(self._session.execute(direct_stmt).scalars().all())

        group_stmt = (
            select(Role.slug)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .join(
                GroupMembership,
                GroupMembership.group_id == RoleAssignment.principal_id,
            )
            .join(Group, Group.id == GroupMembership.group_id)
            .where(
                RoleAssignment.principal_type == PrincipalType.GROUP,
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
                GroupMembership.user_id == user_id,
                Group.is_active == true(),
                self._rbac.build_group_source_filter(),
            )
        )
        role_slugs.update(self._session.execute(group_stmt).scalars().all())

        return sorted(slug for slug in role_slugs if slug)

    def _workspace_ids_with_access(self, *, user: User) -> set[UUID]:
        workspace_ids: set[UUID] = set()

        legacy_stmt = select(UserRoleAssignment.workspace_id).where(
            UserRoleAssignment.user_id == user.id,
            UserRoleAssignment.workspace_id.is_not(None),
        )
        workspace_ids.update(
            workspace_id
            for workspace_id in self._session.execute(legacy_stmt).scalars().all()
            if workspace_id is not None
        )

        direct_stmt = select(RoleAssignment.scope_id).where(
            RoleAssignment.principal_type == PrincipalType.USER,
            RoleAssignment.principal_id == user.id,
            RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
            RoleAssignment.scope_id.is_not(None),
        )
        workspace_ids.update(
            workspace_id
            for workspace_id in self._session.execute(direct_stmt).scalars().all()
            if workspace_id is not None
        )

        group_stmt = (
            select(RoleAssignment.scope_id)
            .join(
                GroupMembership,
                GroupMembership.group_id == RoleAssignment.principal_id,
            )
            .join(Group, Group.id == GroupMembership.group_id)
            .where(
                RoleAssignment.principal_type == PrincipalType.GROUP,
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id.is_not(None),
                GroupMembership.user_id == user.id,
                Group.is_active == true(),
                self._rbac.build_group_source_filter(),
            )
        )
        workspace_ids.update(
            workspace_id
            for workspace_id in self._session.execute(group_stmt).scalars().all()
            if workspace_id is not None
        )

        return workspace_ids

    def _default_workspace_role_ids(self) -> list[UUID]:
        role = self._rbac.get_role_by_slug(slug=_WORKSPACE_MEMBER_SLUG)
        if role is None:
            return []
        return [role.id]

    def _assign_default_roles(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        role_slugs: Sequence[str],
    ) -> None:
        for slug in role_slugs:
            role = self._rbac.get_role_by_slug(slug=slug)
            if role is None:
                continue
            try:
                self._rbac.assign_role_if_missing(
                    user_id=user_id,
                    role_id=role.id,
                    workspace_id=workspace_id,
                )
            except ScopeMismatchError:
                continue

    def _assign_roles_to_member(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        role_ids: Sequence[UUID],
    ) -> None:
        for role_id in role_ids:
            try:
                self._rbac.assign_role_if_missing(
                    user_id=user_id,
                    role_id=role_id,
                    workspace_id=workspace_id,
                )
            except RoleNotFoundError as exc:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc
            except ScopeMismatchError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc
            except RoleConflictError:
                continue

    def _validate_member_target_user(self, *, user_id: UUID) -> User:
        user = self._users_repo.get_by_id_basic(user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if not user.is_active:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="User must be active to be a workspace member",
            )
        if user.is_service_account:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Service accounts cannot be workspace members",
            )
        return user

    def _validate_member_role_ids(self, *, role_ids: Sequence[UUID]) -> None:
        requested_ids = tuple(dict.fromkeys(role_ids))
        if not requested_ids:
            return

        stmt = (
            select(Role)
            .options(
                selectinload(Role.permissions).selectinload(RolePermission.permission),
            )
            .where(Role.id.in_(requested_ids))
        )
        roles = list(self._session.execute(stmt).scalars().all())
        role_by_id = {role.id: role for role in roles}

        missing_role_ids = [str(role_id) for role_id in requested_ids if role_id not in role_by_id]
        if missing_role_ids:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Roles not found: {', '.join(missing_role_ids)}",
            )

        invalid_scope_role_ids = sorted(
            str(role_id)
            for role_id in requested_ids
            if not role_allows_scope(role_by_id[role_id].slug, ScopeType.WORKSPACE)
        )
        if invalid_scope_role_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "role_ids must be assignable to workspace scope: "
                    + ", ".join(invalid_scope_role_ids)
                ),
            )

        non_member_role_ids = sorted(
            str(role_id)
            for role_id in requested_ids
            if not role_grants_workspace_access(role_by_id[role_id])
        )
        if non_member_role_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "role_ids must grant workspace access: "
                    + ", ".join(non_member_role_ids)
                ),
            )

    def _load_effective_member(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> EffectiveWorkspaceMember:
        member = self._effective_members.member_by_user_id(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if member is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load workspace member",
            )
        return member

    def _replace_member_roles(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        role_ids: Sequence[UUID],
    ) -> None:
        desired_role_ids = set(role_ids or self._default_workspace_role_ids())
        direct_assignments = self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        for assignment in direct_assignments:
            if assignment.role_id in desired_role_ids:
                continue
            self._rbac.delete_assignment(
                assignment_id=assignment.id,
                workspace_id=workspace_id,
            )

        remaining_legacy_role_ids = {
            assignment.role_id
            for assignment in self._get_workspace_assignments(
                workspace_id=workspace_id,
                user_id=user_id,
            )
        }
        direct_principal_assignments = self._get_direct_user_principal_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        for assignment in direct_principal_assignments:
            if (
                assignment.role_id in desired_role_ids
                or assignment.role_id in remaining_legacy_role_ids
            ):
                continue
            self._rbac.delete_principal_assignment(assignment_id=assignment.id)

        self._assign_roles_to_member(
            user_id=user_id,
            workspace_id=workspace_id,
            role_ids=list(desired_role_ids),
        )
        self._ensure_owner_retained(workspace_id)

    def _ensure_owner_retained(self, workspace_id: UUID) -> None:
        owner_role = self._rbac.get_role_by_slug(slug=_WORKSPACE_OWNER_SLUG)
        if owner_role is None:
            return
        legacy_owner = self._session.execute(
            select(UserRoleAssignment.id).where(
                UserRoleAssignment.role_id == owner_role.id,
                UserRoleAssignment.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()
        if legacy_owner is not None:
            return

        direct_owner = self._session.execute(
            select(RoleAssignment.id).where(
                RoleAssignment.principal_type == PrincipalType.USER,
                RoleAssignment.role_id == owner_role.id,
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
            )
        ).scalar_one_or_none()
        if direct_owner is not None:
            return

        group_owner = self._session.execute(
            select(RoleAssignment.id)
            .join(
                Group,
                and_(
                    RoleAssignment.principal_type == PrincipalType.GROUP,
                    RoleAssignment.principal_id == Group.id,
                ),
            )
            .where(
                RoleAssignment.role_id == owner_role.id,
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
                Group.is_active == true(),
                self._rbac.build_group_source_filter(),
            )
        ).scalar_one_or_none()
        if group_owner is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Workspace must retain at least one owner",
            )


__all__ = ["WorkspacesService"]
