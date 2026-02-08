"""Workspace domain services aligned with the new RBAC model."""

from __future__ import annotations

import logging
import re
import shutil
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.cursor_listing import ResolvedCursorSort, paginate_sequence_cursor
from ade_api.common.logging import log_context
from ade_api.common.search import matches_tokens, parse_q
from ade_api.features.rbac import (
    AssignmentError,
    RbacService,
    RoleConflictError,
    RoleImmutableError,
    RoleNotFoundError,
    RoleValidationError,
    ScopeMismatchError,
)
from ade_db.models import (
    Role,
    RolePermission,
    User,
    UserRoleAssignment,
    Workspace,
    WorkspaceMembership,
)
from ade_api.settings import Settings

from ..users.repository import UsersRepository
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
                profile = WorkspaceOut(
                    id=workspace.id,
                    name=workspace.name,
                    slug=workspace.slug,
                    roles=[],
                    permissions=sorted(permissions),
                    is_default=False,
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

            membership = self._repo.get_membership_for_workspace(
                user_id=user_id,
                workspace_id=workspace_id,
            )
            if membership is None:
                logger.warning(
                    "workspace.profile.membership_not_found",
                    extra=log_context(user_id=user_id, workspace_id=workspace_id),
                )
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="Workspace not found",
                )

            roles = self._workspace_roles_for_user(
                user_id=user_id,
                workspace_id=workspace_id,
            )
            permissions = self._rbac.get_workspace_permissions_for_user(
                user=user,
                workspace_id=workspace_id,
            )
            profile = WorkspaceOut(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                roles=sorted(role.slug for role in roles),
                permissions=sorted(permissions),
                is_default=membership.is_default,
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
        if membership is None:
            logger.warning(
                "workspace.profile.no_default_membership",
                extra=log_context(user_id=user_id),
            )
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="No default workspace configured",
            )
        workspace_identifier = membership.workspace_id
        roles = self._workspace_roles_for_user(
            user_id=user_id,
            workspace_id=workspace_identifier,
        )
        permissions = self._rbac.get_workspace_permissions_for_user(
            user=user,
            workspace_id=workspace_identifier,
        )
        profile = WorkspaceOut(
            id=membership.workspace_id,
            name=membership.workspace.name if membership.workspace else "",
            slug=membership.workspace.slug if membership.workspace else "",
            roles=sorted(role.slug for role in roles),
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
                profiles.append(
                    WorkspaceOut(
                        id=workspace.id,
                        name=workspace.name,
                        slug=workspace.slug,
                        roles=[],
                        permissions=sorted(permissions),
                        is_default=False,
                        processing_paused=self._processing_paused(workspace),
                    )
                )
            profiles.sort(key=lambda profile: profile.slug)
        else:
            memberships = self._repo.list_for_user(user_id=user_id)
            for membership in memberships:
                roles = self._workspace_roles_for_user(
                    user_id=user_id,
                    workspace_id=membership.workspace_id,
                )
                permissions = self._rbac.get_workspace_permissions_for_user(
                    user=user,
                    workspace_id=membership.workspace_id,
                )
                profiles.append(
                    WorkspaceOut(
                        id=membership.workspace_id,
                        name=membership.workspace.name if membership.workspace else "",
                        slug=membership.workspace.slug if membership.workspace else "",
                        roles=sorted(role.slug for role in roles),
                        permissions=sorted(permissions),
                        is_default=membership.is_default,
                        processing_paused=self._processing_paused(membership.workspace),
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
        return WorkspacePage(items=page_result.items, meta=page_result.meta, facets=page_result.facets)

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
        roles = self._workspace_roles_for_user(
            user_id=user.id,
            workspace_id=workspace_id,
        )
        profile = WorkspaceOut(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            roles=sorted(role.slug for role in roles),
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
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
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
        include_inactive = any(
            parsed.field.id == "isActive" for parsed in parsed_filters
        )
        assignments = self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=None,
            include_inactive=include_inactive,
        )
        grouped: dict[UUID, list[UserRoleAssignment]] = defaultdict(list)
        for assignment in assignments:
            grouped[assignment.user_id].append(assignment)
        members = [
            self._serialize_member(group)
            for group in grouped.values()
            if evaluate_member_filters(group, parsed_filters, join_operator=join_operator)
        ]
        if q:
            tokens = parse_q(q).tokens
            members = [
                member
                for member in members
                if matches_tokens(
                    tokens,
                    [str(member.user_id), *member.role_slugs],
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
        return WorkspaceMemberPage(items=page_result.items, meta=page_result.meta, facets=page_result.facets)

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

        for role_id in payload.role_ids:
            try:
                self._rbac.assign_role_if_missing(
                    user_id=payload.user_id,
                    role_id=role_id,
                    workspace_id=workspace_id,
                )
            except (RoleNotFoundError, AssignmentError) as exc:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
            except ScopeMismatchError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc

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

        assignments = self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=payload.user_id,
        )
        if not assignments:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create workspace member",
            )
        return self._serialize_member(assignments)

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

        assignments = self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not assignments:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )
        return self._serialize_member(assignments)

    def remove_workspace_member(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> None:
        self._ensure_workspace(workspace_id)

        assignments = self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not assignments:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )

        for assignment in assignments:
            self._rbac.delete_assignment(
                assignment_id=assignment.id,
                workspace_id=workspace_id,
            )
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
        try:
            role = self._rbac.update_role(
                role_id=role_id,
                name=payload.name,
                description=payload.description,
                permissions=payload.permissions,
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

    def _serialize_member(self, assignments: Sequence[UserRoleAssignment]) -> WorkspaceMemberOut:
        assignments = list(assignments)
        if not assignments:
            raise ValueError("workspace member requires at least one assignment")
        user_id = assignments[0].user_id
        role_ids = [assignment.role_id for assignment in assignments]
        role_slugs = [
            assignment.role.slug if assignment.role is not None else ""
            for assignment in assignments
        ]
        created_at = min(assignment.created_at for assignment in assignments)
        return WorkspaceMemberOut(
            user_id=user_id,
            role_ids=role_ids,
            role_slugs=role_slugs,
            created_at=created_at,
        )

    def _group_members(self, assignments: list[UserRoleAssignment]) -> list[WorkspaceMemberOut]:
        grouped: dict[UUID, list[UserRoleAssignment]] = defaultdict(list)
        for assignment in assignments:
            grouped[assignment.user_id].append(assignment)
        return [self._serialize_member(group) for group in grouped.values()]

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

    def _workspace_roles_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> list[Role]:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.workspace_id == workspace_id,
            )
        )
        result = self._session.execute(stmt)
        return list(result.scalars().all())

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

    def _replace_member_roles(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        role_ids: Sequence[UUID],
    ) -> None:
        criteria = [
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.workspace_id == workspace_id,
        ]
        if role_ids:
            criteria.append(~UserRoleAssignment.role_id.in_(role_ids))
        self._session.execute(delete(UserRoleAssignment).where(*criteria))
        self._assign_roles_to_member(
            user_id=user_id,
            workspace_id=workspace_id,
            role_ids=role_ids or self._default_workspace_role_ids(),
        )
        self._ensure_owner_retained(workspace_id)

    def _ensure_owner_retained(self, workspace_id: UUID) -> None:
        owner_role = self._rbac.get_role_by_slug(slug=_WORKSPACE_OWNER_SLUG)
        if owner_role is None:
            return
        result = self._session.execute(
            select(UserRoleAssignment.id).where(
                UserRoleAssignment.role_id == owner_role.id,
                UserRoleAssignment.workspace_id == workspace_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Workspace must retain at least one owner",
            )

__all__ = ["WorkspacesService"]
