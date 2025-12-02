from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, Security, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ade_api.app.dependencies import get_current_principal, get_db_session
from ade_api.common.pagination import PageParams, paginate_sequence
from ade_api.core.auth.principal import AuthenticatedPrincipal
from ade_api.core.http import require_csrf
from ade_api.core.models import Role, User, UserRoleAssignment, Workspace, WorkspaceMembership
from ade_api.core.rbac.types import ScopeType
from ade_api.features.rbac.schemas import (
    PermissionOut,
    PermissionPage,
    RoleAssignmentOut,
    RoleAssignmentPage,
    RoleCreate,
    RoleOut,
    RolePage,
    RoleUpdate,
    UserRolesEnvelope,
    UserRoleSummary,
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceMemberPage,
    WorkspaceMemberUpdate,
)
from ade_api.features.rbac.service import (
    AssignmentError,
    AssignmentNotFoundError,
    RbacService,
    RoleConflictError,
    RoleImmutableError,
    RoleNotFoundError,
    RoleValidationError,
    ScopeMismatchError,
    _role_permissions,
)

router = APIRouter(tags=["rbac"])

user_roles_router = APIRouter(
    prefix="/users/{user_id}/roles",
    tags=["rbac"],
)

workspace_members_router = APIRouter(
    prefix="/workspaces/{workspace_id}/members",
    tags=["rbac"],
)

PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PageDep = Annotated[PageParams, Depends()]


# ---------------------------------------------------------------------------
# Helpers for serialization and permission checks
# ---------------------------------------------------------------------------


def _serialize_role(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        slug=role.slug,
        name=role.name,
        description=role.description,
        permissions=[
            rp.permission.key
            for rp in role.permissions
            if rp.permission is not None
        ],
        is_system=role.is_system,
        is_editable=role.is_editable,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _serialize_user_role(assignment: UserRoleAssignment) -> UserRoleSummary:
    role_slug = assignment.role.slug if assignment.role is not None else ""
    return UserRoleSummary(
        role_id=assignment.role_id,
        role_slug=role_slug,
        created_at=assignment.created_at,
    )


def _serialize_assignment(assignment: UserRoleAssignment) -> RoleAssignmentOut:
    return RoleAssignmentOut(
        id=assignment.id,
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        role_slug=assignment.role.slug if assignment.role is not None else "",
        scope_type=assignment.scope_type,
        scope_id=assignment.scope_id,
        created_at=assignment.created_at,
    )


def _serialize_member(assignments: Iterable[UserRoleAssignment]) -> WorkspaceMemberOut:
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


async def _ensure_global_permission(
    *,
    service: RbacService,
    principal: AuthenticatedPrincipal,
    permission_key: str,
) -> None:
    ok = await service.has_permission_for_user_id(
        user_id=principal.user_id,
        permission_key=permission_key,
        workspace_id=None,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


async def _ensure_workspace_permission(
    *,
    service: RbacService,
    principal: AuthenticatedPrincipal,
    permission_key: str,
    workspace_id: UUID,
) -> None:
    ok = await service.has_permission_for_user_id(
        user_id=principal.user_id,
        permission_key=permission_key,
        workspace_id=workspace_id,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


# ---------------------------------------------------------------------------
# Permission catalog
# ---------------------------------------------------------------------------


@router.get(
    "/permissions",
    response_model=PermissionPage,
    response_model_exclude_none=True,
    summary="List permissions",
)
async def list_permissions(
    page: PageDep,
    principal: PrincipalDep,
    session: SessionDep,
    scope: Annotated[
        ScopeType,
        Query(
            description="Scope to filter permissions by",
        ),
    ] = ScopeType.GLOBAL,
) -> PermissionPage:
    service = RbacService(session=session)
    # Require ability to read roles/permissions
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    permissions = await service.list_permissions(scope=scope)
    items = [
        PermissionOut(
            id=permission.id,
            key=permission.key,
            resource=permission.resource,
            action=permission.action,
            scope_type=permission.scope_type,
            label=permission.label,
            description=permission.description,
        )
        for permission in permissions
    ]
    paged = paginate_sequence(
        items,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return PermissionPage(**paged.model_dump())


# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------


@router.get(
    "/roles",
    response_model=RolePage,
    response_model_exclude_none=True,
    summary="List role definitions",
)
async def list_roles(
    page: PageDep,
    principal: PrincipalDep,
    session: SessionDep,
    scope: Annotated[
        ScopeType,
        Query(
            description="Scope to filter roles by",
        ),
    ] = ScopeType.GLOBAL,
) -> RolePage:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    role_page = await service.list_roles_for_scope(
        scope=scope,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return RolePage(
        items=[_serialize_role(role) for role in role_page.items],
        page=role_page.page,
        page_size=role_page.page_size,
        has_next=role_page.has_next,
        has_previous=role_page.has_previous,
        total=role_page.total,
    )


@router.post(
    "/roles",
    dependencies=[Security(require_csrf)],
    response_model=RoleOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create a role",
)
async def create_role(
    payload: RoleCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> RoleOut:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    actor = await session.get(User, principal.user_id)
    try:
        role = await service.create_role(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            permissions=payload.permissions,
            actor=actor,
        )
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _serialize_role(role)


async def _load_role(
    role_id: Annotated[UUID, Path(description="Role identifier")],
    session: SessionDep,
) -> Role:
    service = RbacService(session=session)
    role = await service.get_role(role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.get(
    "/roles/{role_id}",
    response_model=RoleOut,
    response_model_exclude_none=True,
    summary="Retrieve a role definition",
)
async def read_role(
    role: Annotated[Role, Depends(_load_role)],
    principal: PrincipalDep,
    session: SessionDep,
) -> RoleOut:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )
    return _serialize_role(role)


@router.patch(
    "/roles/{role_id}",
    dependencies=[Security(require_csrf)],
    response_model=RoleOut,
    response_model_exclude_none=True,
    summary="Update an existing role",
)
async def update_role(
    payload: RoleUpdate,
    role: Annotated[Role, Depends(_load_role)],
    principal: PrincipalDep,
    session: SessionDep,
) -> RoleOut:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    actor = await session.get(User, principal.user_id)

    try:
        updated = await service.update_role(
            role_id=role.id,
            name=payload.name or role.name,
            description=(
                payload.description
                if payload.description is not None
                else role.description
            ),
            permissions=payload.permissions or _role_permissions(role),
            actor=actor,
        )
    except RoleImmutableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _serialize_role(updated)


@router.delete(
    "/roles/{role_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a role",
)
async def delete_role(
    role_id: Annotated[UUID, Path(description="Role identifier")],
    principal: PrincipalDep,
    session: SessionDep,
) -> Response:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    try:
        await service.delete_role(role_id=role_id)
    except RoleImmutableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoleNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found") from None

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Admin assignments listing (optional)
# ---------------------------------------------------------------------------


@router.get(
    "/role-assignments",
    response_model=RoleAssignmentPage,
    response_model_exclude_none=True,
    summary="List role assignments (admin view)",
)
async def list_assignments(
    page: PageDep,
    principal: PrincipalDep,
    session: SessionDep,
    scope: Annotated[
        ScopeType,
        Query(
            description="Scope to filter assignments by",
        ),
    ] = ScopeType.GLOBAL,
    scope_id: Annotated[
        UUID | None,
        Query(
            description="Scope ID (required when scope=workspace)",
        ),
    ] = None,
    user_id: Annotated[
        UUID | None,
        Query(
            description="Filter by user id",
        ),
    ] = None,
    role_id: Annotated[
        UUID | None,
        Query(
            description="Filter by role id",
        ),
    ] = None,
) -> RoleAssignmentPage:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    if scope == ScopeType.WORKSPACE and scope_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scope_id is required when scope=workspace",
        )
    if scope == ScopeType.GLOBAL:
        scope_id = None

    assignments = await service.list_assignments(
        scope_type=scope,
        scope_id=scope_id,
        user_id=user_id,
        role_id=role_id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return RoleAssignmentPage(
        items=[_serialize_assignment(item) for item in assignments.items],
        page=assignments.page,
        page_size=assignments.page_size,
        has_next=assignments.has_next,
        has_previous=assignments.has_previous,
        total=assignments.total,
    )


# ---------------------------------------------------------------------------
# Global role assignments per user
# ---------------------------------------------------------------------------


async def _load_user_role_assignments(
    *,
    service: RbacService,
    user_id: UUID,
) -> list[UserRoleAssignment]:
    assignments_page = await service.list_assignments(
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
        user_id=user_id,
        role_id=None,
        page=1,
        page_size=1000,
        include_total=False,
    )
    return assignments_page.items


@user_roles_router.get(
    "",
    response_model=UserRolesEnvelope,
    summary="List global roles assigned to a user",
)
async def list_user_roles(
    user_id: Annotated[UUID, Path(description="User identifier")],
    principal: PrincipalDep,
    session: SessionDep,
) -> UserRolesEnvelope:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    assignments = await _load_user_role_assignments(service=service, user_id=user_id)
    return UserRolesEnvelope(
        user_id=user_id,
        roles=[_serialize_user_role(assignment) for assignment in assignments],
    )


@user_roles_router.put(
    "/{role_id}",
    dependencies=[Security(require_csrf)],
    response_model=UserRolesEnvelope,
    summary="Assign a global role to a user (idempotent)",
)
async def assign_user_role(
    user_id: Annotated[UUID, Path(description="User identifier")],
    role_id: Annotated[UUID, Path(description="Role identifier")],
    principal: PrincipalDep,
    session: SessionDep,
) -> UserRolesEnvelope:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    try:
        await service.assign_role_if_missing(
            user_id=user_id,
            role_id=role_id,
            scope_type=ScopeType.GLOBAL,
            scope_id=None,
        )
    except (RoleNotFoundError, AssignmentError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    assignments = await _load_user_role_assignments(service=service, user_id=user_id)
    return UserRolesEnvelope(
        user_id=user_id,
        roles=[_serialize_user_role(assignment) for assignment in assignments],
    )


@user_roles_router.delete(
    "/{role_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a global role from a user",
)
async def remove_user_role(
    user_id: Annotated[UUID, Path(description="User identifier")],
    role_id: Annotated[UUID, Path(description="Role identifier")],
    principal: PrincipalDep,
    session: SessionDep,
) -> Response:
    service = RbacService(session=session)
    await _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    assignment = await service.get_assignment_for_user_role(
        user_id=user_id,
        role_id=role_id,
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
    )
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role assignment not found")

    try:
        await service.delete_assignment(
            assignment_id=assignment.id,
            scope_type=ScopeType.GLOBAL,
            scope_id=None,
        )
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Workspace membership
# ---------------------------------------------------------------------------


async def _get_workspace_assignments(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID | None = None,
) -> list[UserRoleAssignment]:
    stmt = (
        select(UserRoleAssignment)
        .options(
            selectinload(UserRoleAssignment.role).selectinload(Role.permissions),
            selectinload(UserRoleAssignment.user),
        )
        .where(
            UserRoleAssignment.scope_type == ScopeType.WORKSPACE,
            UserRoleAssignment.scope_id == workspace_id,
        )
    )
    if user_id:
        stmt = stmt.where(UserRoleAssignment.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _group_members(assignments: list[UserRoleAssignment]) -> list[WorkspaceMemberOut]:
    grouped: dict[UUID, list[UserRoleAssignment]] = defaultdict(list)
    for assignment in assignments:
        grouped[assignment.user_id].append(assignment)
    return [_serialize_member(group) for group in grouped.values()]


async def _ensure_membership(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
) -> WorkspaceMembership:
    result = await session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    membership = WorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        is_default=False,
    )
    session.add(membership)
    await session.flush([membership])
    return membership


async def _delete_membership_if_exists(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    result = await session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is not None:
        await session.delete(membership)


@workspace_members_router.get(
    "",
    response_model=WorkspaceMemberPage,
    response_model_exclude_none=True,
    summary="List workspace members with their roles",
)
async def list_workspace_members(
    workspace_id: Annotated[UUID, Path(description="Workspace identifier")],
    page: PageDep,
    principal: PrincipalDep,
    session: SessionDep,
    user_id: Annotated[
        UUID | None,
        Query(
            description="Optional filter by user id",
        ),
    ] = None,
) -> WorkspaceMemberPage:
    service = RbacService(session=session)

    # Check workspace exists
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    await _ensure_workspace_permission(
        service=service,
        principal=principal,
        permission_key="workspace.members.read",
        workspace_id=workspace_id,
    )

    assignments = await _get_workspace_assignments(
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    members = _group_members(assignments)
    paged = paginate_sequence(
        members,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return WorkspaceMemberPage(**paged.model_dump())


@workspace_members_router.post(
    "",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a workspace member with roles",
)
async def add_workspace_member(
    workspace_id: Annotated[UUID, Path(description="Workspace identifier")],
    payload: WorkspaceMemberCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> WorkspaceMemberOut:
    service = RbacService(session=session)

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    await _ensure_workspace_permission(
        service=service,
        principal=principal,
        permission_key="workspace.members.manage",
        workspace_id=workspace_id,
    )

    if not payload.role_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="role_ids must include at least one role",
        )

    for role_id in payload.role_ids:
        try:
            await service.assign_role_if_missing(
                user_id=payload.user_id,
                role_id=role_id,
                scope_type=ScopeType.WORKSPACE,
                scope_id=workspace_id,
            )
        except (RoleNotFoundError, AssignmentError) as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ScopeMismatchError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    await _ensure_membership(
        session=session,
        workspace_id=workspace_id,
        user_id=payload.user_id,
    )

    assignments = await _get_workspace_assignments(
        session=session,
        workspace_id=workspace_id,
        user_id=payload.user_id,
    )
    if not assignments:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace member",
        )
    return _serialize_member(assignments)


@workspace_members_router.put(
    "/{user_id}",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    summary="Replace workspace member roles",
)
async def update_workspace_member(
    workspace_id: Annotated[UUID, Path(description="Workspace identifier")],
    user_id: Annotated[UUID, Path(description="User identifier")],
    payload: WorkspaceMemberUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> WorkspaceMemberOut:
    service = RbacService(session=session)

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    await _ensure_workspace_permission(
        service=service,
        principal=principal,
        permission_key="workspace.members.manage",
        workspace_id=workspace_id,
    )

    if not payload.role_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="role_ids must include at least one role",
        )

    existing = await _get_workspace_assignments(
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    await _ensure_membership(
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    existing_by_role = {assignment.role_id: assignment for assignment in existing}
    target_roles = set(payload.role_ids)
    to_add = target_roles - set(existing_by_role.keys())
    to_remove = set(existing_by_role.keys()) - target_roles

    for role_id in to_add:
        try:
            await service.assign_role(
                user_id=user_id,
                role_id=role_id,
                scope_type=ScopeType.WORKSPACE,
                scope_id=workspace_id,
            )
        except (RoleNotFoundError, AssignmentError) as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ScopeMismatchError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        except RoleConflictError:
            # Another request raced; ignore and continue
            continue

    for role_id in to_remove:
        assignment = existing_by_role.get(role_id)
        if assignment is None:
            continue
        try:
            await service.delete_assignment(
                assignment_id=assignment.id,
                scope_type=ScopeType.WORKSPACE,
                scope_id=workspace_id,
            )
        except AssignmentNotFoundError:
            continue
        except ScopeMismatchError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    updated = await _get_workspace_assignments(
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace member not found")
    return _serialize_member(updated)


@workspace_members_router.delete(
    "/{user_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a workspace member",
)
async def remove_workspace_member(
    workspace_id: Annotated[UUID, Path(description="Workspace identifier")],
    user_id: Annotated[UUID, Path(description="User identifier")],
    principal: PrincipalDep,
    session: SessionDep,
) -> Response:
    service = RbacService(session=session)

    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    await _ensure_workspace_permission(
        service=service,
        principal=principal,
        permission_key="workspace.members.manage",
        workspace_id=workspace_id,
    )

    assignments = await _get_workspace_assignments(
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if not assignments:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace member not found")

    for assignment in assignments:
        await service.delete_assignment(
            assignment_id=assignment.id,
            scope_type=ScopeType.WORKSPACE,
            scope_id=workspace_id,
        )
    await _delete_membership_if_exists(
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router", "user_roles_router", "workspace_members_router"]
