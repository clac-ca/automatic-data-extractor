"""Workspace domain services aligned with the new RBAC model."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, cast

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ade_api.common.logging import log_context
from ade_api.common.pagination import Page, paginate_sequence
from ade_api.core.models import (
    Role,
    RolePermission,
    ScopeType,
    User,
    UserRoleAssignment,
    Workspace,
    WorkspaceMembership,
)
from ade_api.features.rbac import (
    AssignmentError,
    RbacService,
    RoleConflictError,
    RoleImmutableError,
    RoleNotFoundError,
    RoleValidationError,
    ScopeMismatchError,
)

from ..users.repository import UsersRepository
from .repository import WorkspacesRepository
from .schemas import (
    WorkspaceDefaultSelectionOut,
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceMemberPage,
    WorkspaceMemberUpdate,
    WorkspaceOut,
)

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

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._repo = WorkspacesRepository(session)
        self._users_repo = UsersRepository(session)
        self._rbac = RbacService(session=session)

    # ------------------------------------------------------------------
    # Workspace profiles
    # ------------------------------------------------------------------
    async def get_workspace_profile(
        self,
        *,
        user: User,
        workspace_id: str | None,
    ) -> WorkspaceOut:
        """Return the workspace membership profile for ``user``."""

        user_id = cast(str, user.id)
        logger.debug(
            "workspace.profile.start",
            extra=log_context(user_id=user_id, workspace_id=workspace_id),
        )

        global_permissions = await self._rbac.get_global_permissions_for_user(user=user)
        is_global_admin = bool(_GLOBAL_WORKSPACE_PERMS & global_permissions)

        if workspace_id is not None:
            workspace = await self._repo.get_workspace(workspace_id)
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
                permissions = await self._rbac.get_workspace_permissions_for_user(
                    user=user, workspace_id=workspace_id
                )
                profile = WorkspaceOut(
                    id=cast(str, workspace.id),
                    name=workspace.name,
                    slug=workspace.slug,
                    roles=[],
                    permissions=sorted(permissions),
                    is_default=False,
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

            membership = await self._repo.get_membership_for_workspace(
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

            roles = await self._workspace_roles_for_user(
                user_id=user_id,
                workspace_id=workspace_id,
            )
            permissions = await self._rbac.get_workspace_permissions_for_user(
                user=user,
                workspace_id=workspace_id,
            )
            profile = WorkspaceOut(
                id=cast(str, workspace.id),
                name=workspace.name,
                slug=workspace.slug,
                roles=sorted(role.slug for role in roles),
                permissions=sorted(permissions),
                is_default=membership.is_default,
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

        membership = await self._repo.get_default_membership(user_id=user_id)
        if membership is None:
            logger.warning(
                "workspace.profile.no_default_membership",
                extra=log_context(user_id=user_id),
            )
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="No default workspace configured",
            )
        workspace_identifier = cast(str, membership.workspace_id)
        roles = await self._workspace_roles_for_user(
            user_id=user_id,
            workspace_id=workspace_identifier,
        )
        permissions = await self._rbac.get_workspace_permissions_for_user(
            user=user,
            workspace_id=workspace_identifier,
        )
        profile = WorkspaceOut(
            id=cast(str, membership.workspace_id),
            name=membership.workspace.name if membership.workspace else "",
            slug=membership.workspace.slug if membership.workspace else "",
            roles=sorted(role.slug for role in roles),
            permissions=sorted(permissions),
            is_default=membership.is_default,
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

    async def list_memberships(
        self,
        *,
        user: User,
        global_permissions: frozenset[str] | None = None,
    ) -> list[WorkspaceOut]:
        """Return workspace profiles associated with ``user``."""

        user_id = cast(str, user.id)
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
            global_permissions = await self._rbac.get_global_permissions_for_user(
                user=user
            )
        is_global_admin = bool(_GLOBAL_WORKSPACE_PERMS & global_permissions)

        profiles: list[WorkspaceOut] = []
        if is_global_admin:
            workspaces = await self._repo.list_all()
            for workspace in workspaces:
                permissions = await self._rbac.get_workspace_permissions_for_user(
                    user=user, workspace_id=cast(str, workspace.id)
                )
                profiles.append(
                    WorkspaceOut(
                        id=cast(str, workspace.id),
                        name=workspace.name,
                        slug=workspace.slug,
                        roles=[],
                        permissions=sorted(permissions),
                        is_default=False,
                    )
                )
            profiles.sort(key=lambda profile: profile.slug)
        else:
            memberships = await self._repo.list_for_user(user_id=user_id)
            for membership in memberships:
                roles = await self._workspace_roles_for_user(
                    user_id=user_id,
                    workspace_id=cast(str, membership.workspace_id),
                )
                permissions = await self._rbac.get_workspace_permissions_for_user(
                    user=user,
                    workspace_id=cast(str, membership.workspace_id),
                )
                profiles.append(
                    WorkspaceOut(
                        id=cast(str, membership.workspace_id),
                        name=membership.workspace.name if membership.workspace else "",
                        slug=membership.workspace.slug if membership.workspace else "",
                        roles=sorted(role.slug for role in roles),
                        permissions=sorted(permissions),
                        is_default=membership.is_default,
                    )
                )
            profiles.sort(key=lambda profile: profile.slug)

        logger.info(
            "workspace.memberships.list.success",
            extra=log_context(user_id=user_id, count=len(profiles)),
        )
        return profiles

    async def list_workspaces(
        self,
        *,
        user: User,
        page: int,
        page_size: int,
        include_total: bool,
        global_permissions: frozenset[str] | None = None,
    ) -> Page[WorkspaceOut]:
        memberships = await self.list_memberships(
            user=user,
            global_permissions=global_permissions,
        )
        page_result = paginate_sequence(
            memberships,
            page=page,
            page_size=page_size,
            include_total=include_total,
        )
        return page_result

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    async def create_workspace(
        self,
        *,
        user: User,
        name: str,
        slug: str | None,
        owner_user_id: str | None = None,
        settings: Mapping[str, object] | None = None,
    ) -> WorkspaceOut:
        slug_value = _slugify(slug or name)
        if not slug_value:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Workspace slug is required",
            )
        await self._ensure_slug_available(slug_value)

        owner_id = owner_user_id or cast(str, user.id)
        owner = await self._users_repo.get_by_id(owner_id)
        if owner is None or not owner.is_active:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Owner not found",
            )

        logger.debug(
            "workspace.create.start",
            extra=log_context(slug=slug_value, owner_id=owner_id),
        )

        try:
            workspace = await self._repo.create_workspace(
                name=name.strip(),
                slug=slug_value,
                settings=settings,
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

        existing_default = await self._repo.get_default_membership(user_id=owner_id)
        membership = await self._repo.create_membership(
            workspace_id=cast(str, workspace.id),
            user_id=owner_id,
            is_default=existing_default is None,
        )

        await self._assign_default_roles(
            user_id=owner_id,
            workspace_id=cast(str, workspace.id),
            role_slugs=[_WORKSPACE_OWNER_SLUG],
        )

        permissions = await self._rbac.get_workspace_permissions_for_user(
            user=owner,
            workspace_id=cast(str, workspace.id),
        )
        profile = WorkspaceOut(
            id=cast(str, workspace.id),
            name=workspace.name,
            slug=workspace.slug,
            roles=[_WORKSPACE_OWNER_SLUG],
            permissions=sorted(permissions),
            is_default=membership.is_default,
        )
        logger.info(
            "workspace.create.success",
            extra=log_context(
                workspace_id=workspace.id,
                slug=workspace.slug,
                owner_id=owner_id,
            ),
        )
        return profile

    async def update_workspace(
        self,
        *,
        user: User,
        workspace_id: str,
        name: str | None,
        slug: str | None,
        settings: Mapping[str, object] | None = None,
    ) -> WorkspaceOut:
        workspace = await self._ensure_workspace(workspace_id)
        slug_value = _slugify(slug) if slug else None
        if slug_value:
            await self._ensure_slug_available(slug_value, current_id=cast(str, workspace.id))

        try:
            workspace = await self._repo.update_workspace(
                workspace,
                name=name.strip() if name else None,
                slug=slug_value,
                settings=settings,
            )
        except IntegrityError as exc:  # pragma: no cover - defensive double check
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace slug already exists",
            ) from exc

        permissions = await self._rbac.get_workspace_permissions_for_user(
            user=user,
            workspace_id=workspace_id,
        )
        membership = await self._repo.get_membership_for_workspace(
            user_id=cast(str, user.id),
            workspace_id=workspace_id,
        )
        roles = await self._workspace_roles_for_user(
            user_id=cast(str, user.id),
            workspace_id=workspace_id,
        )
        profile = WorkspaceOut(
            id=cast(str, workspace.id),
            name=workspace.name,
            slug=workspace.slug,
            roles=sorted(role.slug for role in roles),
            permissions=sorted(permissions),
            is_default=membership.is_default if membership else False,
        )
        return profile

    async def delete_workspace(self, *, workspace_id: str) -> None:
        workspace = await self._ensure_workspace(workspace_id)
        await self._repo.delete_workspace(workspace)
        logger.info(
            "workspace.delete.success",
            extra=log_context(workspace_id=workspace_id),
        )

    async def set_default_workspace(
        self,
        *,
        workspace_id: str,
        user: User,
    ) -> WorkspaceDefaultSelectionOut:
        membership = await self._repo.get_membership_for_workspace(
            user_id=cast(str, user.id),
            workspace_id=workspace_id,
        )
        if membership is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        await self._session.execute(
            update(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == cast(str, user.id))
            .values(is_default=False)
        )
        membership.is_default = True
        await self._session.flush()
        return WorkspaceDefaultSelectionOut(
            workspace_id=workspace_id,
            is_default=True,
        )

    # ------------------------------------------------------------------
    # Workspace members
    # ------------------------------------------------------------------
    async def list_workspace_members(
        self,
        *,
        workspace_id: str,
        page: int,
        page_size: int,
        include_total: bool,
        user_id: str | None = None,
    ) -> WorkspaceMemberPage:
        await self._ensure_workspace(workspace_id)
        assignments = await self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        members = self._group_members(assignments)
        page_result = paginate_sequence(
            members,
            page=page,
            page_size=page_size,
            include_total=include_total,
        )
        return WorkspaceMemberPage(**page_result.model_dump())

    async def add_workspace_member(
        self,
        *,
        workspace_id: str,
        payload: WorkspaceMemberCreate,
    ) -> WorkspaceMemberOut:
        await self._ensure_workspace(workspace_id)

        if not payload.role_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="role_ids must include at least one role",
            )

        for role_id in payload.role_ids:
            try:
                await self._rbac.assign_role_if_missing(
                    user_id=cast(str, payload.user_id),
                    role_id=cast(str, role_id),
                    scope_type=ScopeType.WORKSPACE,
                    scope_id=workspace_id,
                )
            except (RoleNotFoundError, AssignmentError) as exc:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
            except ScopeMismatchError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

        membership = await self._repo.get_membership_for_workspace(
            user_id=cast(str, payload.user_id),
            workspace_id=workspace_id,
        )
        if membership is None:
            await self._repo.create_membership(
                workspace_id=workspace_id,
                user_id=cast(str, payload.user_id),
                is_default=False,
            )

        assignments = await self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=cast(str, payload.user_id),
        )
        if not assignments:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create workspace member",
            )
        return self._serialize_member(assignments)

    async def update_workspace_member_roles(
        self,
        *,
        workspace_id: str,
        user_id: str,
        payload: WorkspaceMemberUpdate,
    ) -> WorkspaceMemberOut:
        await self._ensure_workspace(workspace_id)

        if not payload.role_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="role_ids must include at least one role",
            )

        membership = await self._repo.get_membership_for_workspace(
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            await self._repo.create_membership(
                workspace_id=workspace_id,
                user_id=user_id,
                is_default=False,
            )

        await self._replace_member_roles(
            user_id=user_id,
            workspace_id=workspace_id,
            role_ids=[cast(str, role_id) for role_id in payload.role_ids],
        )

        assignments = await self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not assignments:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )
        return self._serialize_member(assignments)

    async def remove_workspace_member(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> None:
        await self._ensure_workspace(workspace_id)

        assignments = await self._get_workspace_assignments(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not assignments:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )

        for assignment in assignments:
            await self._rbac.delete_assignment(
                assignment_id=cast(str, assignment.id),
                scope_type=ScopeType.WORKSPACE,
                scope_id=workspace_id,
            )
        await self._delete_membership_if_exists(
            workspace_id=workspace_id,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Role definitions scoped for workspace use
    # ------------------------------------------------------------------
    async def create_workspace_role(
        self,
        *,
        workspace_id: str,
        payload: RoleCreate,
        actor: User,
    ) -> Role:
        await self._ensure_workspace(workspace_id)
        try:
            return await self._rbac.create_role(
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

    async def update_workspace_role(
        self,
        *,
        workspace_id: str,
        role_id: str,
        payload: RoleUpdate,
        actor: User,
    ) -> Role:
        await self._ensure_workspace(workspace_id)
        try:
            role = await self._rbac.update_role(
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

    async def delete_workspace_role(
        self,
        *,
        workspace_id: str,
        role_id: str,
    ) -> None:
        await self._ensure_workspace(workspace_id)
        assignments = await self._session.execute(
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
            await self._rbac.delete_role(role_id=role_id)
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
    async def _ensure_slug_available(self, slug: str, current_id: str | None = None) -> None:
        existing = await self._repo.get_workspace_by_slug(slug)
        if existing is not None and str(existing.id) != str(current_id or ""):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Workspace slug already exists",
            )

    async def _ensure_workspace(self, workspace_id: str) -> Workspace:
        workspace = await self._repo.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        return workspace

    async def _get_workspace_assignments(
        self,
        *,
        workspace_id: str,
        user_id: str | None = None,
    ) -> list[UserRoleAssignment]:
        stmt = (
            select(UserRoleAssignment)
            .options(
                selectinload(UserRoleAssignment.role).selectinload(RolePermission.permission),
                selectinload(UserRoleAssignment.user),
            )
            .where(
                UserRoleAssignment.scope_type == ScopeType.WORKSPACE,
                UserRoleAssignment.scope_id == workspace_id,
            )
        )
        if user_id:
            stmt = stmt.where(UserRoleAssignment.user_id == user_id)
        result = await self._session.execute(stmt)
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
            user_id=cast(str, user_id),
            role_ids=[cast(str, role_id) for role_id in role_ids],
            role_slugs=role_slugs,
            created_at=created_at,
        )

    def _group_members(self, assignments: list[UserRoleAssignment]) -> list[WorkspaceMemberOut]:
        grouped: dict[str, list[UserRoleAssignment]] = defaultdict(list)
        for assignment in assignments:
            grouped[cast(str, assignment.user_id)].append(assignment)
        return [self._serialize_member(group) for group in grouped.values()]

    async def _delete_membership_if_exists(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> None:
        membership = await self._repo.get_membership_for_workspace(
            user_id=user_id,
            workspace_id=workspace_id,
        )
        if membership is not None:
            await self._repo.delete_membership(membership)

    async def _workspace_roles_for_user(
        self,
        *,
        user_id: str,
        workspace_id: str,
    ) -> list[Role]:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.scope_type == ScopeType.WORKSPACE,
                UserRoleAssignment.scope_id == workspace_id,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _default_workspace_role_ids(self) -> list[str]:
        role = await self._rbac.get_role_by_slug(slug=_WORKSPACE_MEMBER_SLUG)
        if role is None:
            return []
        return [cast(str, role.id)]

    async def _assign_default_roles(
        self,
        *,
        user_id: str,
        workspace_id: str,
        role_slugs: Sequence[str],
    ) -> None:
        for slug in role_slugs:
            role = await self._rbac.get_role_by_slug(slug=slug)
            if role is None:
                continue
            try:
                await self._rbac.assign_role_if_missing(
                    user_id=user_id,
                    role_id=cast(str, role.id),
                    scope_type=ScopeType.WORKSPACE,
                    scope_id=workspace_id,
                )
            except ScopeMismatchError:
                continue

    async def _assign_roles_to_member(
        self,
        *,
        user_id: str,
        workspace_id: str,
        role_ids: Sequence[str],
    ) -> None:
        for role_id in role_ids:
            try:
                await self._rbac.assign_role_if_missing(
                    user_id=user_id,
                    role_id=role_id,
                    scope_type=ScopeType.WORKSPACE,
                    scope_id=workspace_id,
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

    async def _replace_member_roles(
        self,
        *,
        user_id: str,
        workspace_id: str,
        role_ids: Sequence[str],
    ) -> None:
        criteria = [
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.scope_type == ScopeType.WORKSPACE,
            UserRoleAssignment.scope_id == workspace_id,
        ]
        if role_ids:
            criteria.append(~UserRoleAssignment.role_id.in_(role_ids))
        await self._session.execute(delete(UserRoleAssignment).where(*criteria))
        await self._assign_roles_to_member(
            user_id=user_id,
            workspace_id=workspace_id,
            role_ids=role_ids or await self._default_workspace_role_ids(),
        )
        await self._ensure_owner_retained(workspace_id)

    async def _ensure_owner_retained(self, workspace_id: str) -> None:
        owner_role = await self._rbac.get_role_by_slug(slug=_WORKSPACE_OWNER_SLUG)
        if owner_role is None:
            return
        result = await self._session.execute(
            select(UserRoleAssignment.id).where(
                UserRoleAssignment.role_id == owner_role.id,
                UserRoleAssignment.scope_type == ScopeType.WORKSPACE,
                UserRoleAssignment.scope_id == workspace_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Workspace must retain at least one owner",
            )


__all__ = ["WorkspacesService"]
