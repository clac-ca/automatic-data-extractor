"""HTTP endpoints for RBAC role, assignment, and permission management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.shared.core.security import forbidden_response
from ade_api.shared.db.session import get_session
from ade_api.shared.dependency import (
    get_current_identity,
    require_authenticated,
    require_csrf,
    require_global,
    require_permissions_catalog_access,
    require_workspace,
)
from ade_api.shared.pagination import PageParams, paginate_sequence

from ..auth.service import AuthenticatedIdentity
from ..users.models import User
from ..workspaces.service import WorkspacesService
from .models import Permission, Role, ScopeType, UserRoleAssignment
from .registry import PERMISSION_REGISTRY
from .schemas import (
    EffectivePermissionsResponse,
    PermissionCheckRequest,
    PermissionCheckResponse,
    PermissionOut,
    PermissionPage,
    RoleAssignmentCreate,
    RoleAssignmentOut,
    RoleAssignmentPage,
    RoleCreate,
    RoleOut,
    RolePage,
    RoleUpdate,
)
from .service import (
    AssignmentError,
    AssignmentNotFoundError,
    AuthorizationError,
    RbacService,
    ScopeMismatchError,
    RoleConflictError,
    RoleImmutableError,
    RoleNotFoundError,
    RoleValidationError,
    authorize as authorize_permission,
    collect_permission_keys,
)

router = APIRouter(tags=["roles"], dependencies=[Security(require_authenticated)])


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_role(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        slug=role.slug,
        name=role.name,
        description=role.description,
        permissions=[
            permission.permission.key
            for permission in role.permissions
            if permission.permission is not None
        ],
        is_system=role.is_system,
        is_editable=role.is_editable,
        created_at=role.created_at,
        updated_at=role.updated_at,
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


# ---------------------------------------------------------------------------
# Role endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/roles",
    response_model=RolePage,
    response_model_exclude_none=True,
    summary="List role definitions",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks role read permission.",
        },
    },
)
async def list_roles(
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: Annotated[
        ScopeType,
        Query(description="Scope to filter roles by"),
    ] = ScopeType.GLOBAL,
    page: Annotated[PageParams, Depends()],
    _actor: Annotated[User, Security(require_global("roles.read_all"))],
) -> RolePage:
    service = RbacService(session=session)
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
    response_model=RoleOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create a role",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks role management permission.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Role slug already exists.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Role payload is invalid.",
        },
    },
)
async def create_role(
    payload: RoleCreate,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Security(require_global("roles.manage_all"))],
) -> RoleOut:
    service = RbacService(session=session)
    try:
        role = await service.create_role(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            permissions=payload.permissions,
            actor=actor,
        )
    except (RoleConflictError, RoleValidationError) as exc:
        status_code = status.HTTP_409_CONFLICT if isinstance(exc, RoleConflictError) else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return _serialize_role(role)


async def _load_role(
    role_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
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
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to view roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks permission to view the role.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role not found.",
        },
    },
)
async def read_role(
    role: Annotated[Role, Depends(_load_role)],
    _actor: Annotated[User, Security(require_global("roles.read_all"))],
) -> RoleOut:
    return _serialize_role(role)


@router.patch(
    "/roles/{role_id}",
    response_model=RoleOut,
    response_model_exclude_none=True,
    summary="Update a role",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update roles.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Role is not editable.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks permission to modify the role.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role not found.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Role slug or permissions conflict.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Role payload is invalid.",
        },
    },
)
async def update_role(
    payload: RoleUpdate,
    role: Annotated[Role, Depends(_load_role)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Security(require_global("roles.manage_all"))],
) -> RoleOut:
    service = RbacService(session=session)
    try:
        updated = await service.update_role(
            role_id=str(role.id),
            name=payload.name,
            description=payload.description,
            permissions=payload.permissions,
            actor=actor,
        )
    except RoleImmutableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RoleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except RoleNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found") from None

    return _serialize_role(updated)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a role",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to delete roles.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Role is not deletable.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks permission to delete the role.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role not found.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Role is still assigned to users.",
        },
    },
)
async def delete_role(
    role_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[User, Security(require_global("roles.manage_all"))],
) -> None:
    service = RbacService(session=session)
    try:
        await service.delete_role(role_id=role_id)
    except RoleImmutableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoleNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found") from None


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


@router.get(
    "/role-assignments",
    response_model=RoleAssignmentPage,
    response_model_exclude_none=True,
    summary="List global role assignments",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list role assignments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks global role assignment read permission.",
        },
    },
)
async def list_global_role_assignments(
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str | None, Query(min_length=1)] = None,
    role_id: Annotated[str | None, Query(min_length=1)] = None,
    page: Annotated[PageParams, Depends()],
    _actor: Annotated[User, Security(require_global("roles.read_all"))],
) -> RoleAssignmentPage:
    service = RbacService(session=session)
    assignments = await service.list_assignments(
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
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


@router.post(
    "/role-assignments",
    response_model=RoleAssignmentOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a global role to a user",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage role assignments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks global role assignment permission.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "User or role not found.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid role assignment payload.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Assignment already exists.",
        },
    },
)
async def create_global_role_assignment(
    payload: RoleAssignmentCreate,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[User, Security(require_global("roles.manage_all"))],
) -> RoleAssignmentOut:
    service = RbacService(session=session)
    try:
        assignment = await service.assign_role(
            user_id=payload.user_id,
            role_id=payload.role_id,
            scope_type=ScopeType.GLOBAL,
            scope_id=None,
        )
    except (RoleNotFoundError, AssignmentError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _serialize_assignment(assignment)


@router.delete(
    "/role-assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a global role assignment",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage role assignments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks global role assignment permission.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role assignment not found.",
        },
    },
)
async def delete_global_role_assignment(
    assignment_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[User, Security(require_global("roles.manage_all"))],
) -> None:
    service = RbacService(session=session)
    try:
        await service.delete_assignment(
            assignment_id=assignment_id,
            scope_type=ScopeType.GLOBAL,
            scope_id=None,
        )
    except AssignmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get(
    "/workspaces/{workspace_id}/role-assignments",
    response_model=RoleAssignmentPage,
    response_model_exclude_none=True,
    summary="List workspace role assignments",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list assignments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks workspace membership read permission.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found.",
        },
    },
)
async def list_workspace_role_assignments(
    workspace_id: Annotated[str, Path(..., min_length=1)],
    user_id: Annotated[str | None, Query(min_length=1)] = None,
    role_id: Annotated[str | None, Query(min_length=1)] = None,
    *,
    page: Annotated[PageParams, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> RoleAssignmentPage:
    service = RbacService(session=session)
    assignments = await service.list_assignments(
        scope_type=ScopeType.WORKSPACE,
        scope_id=workspace_id,
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


@router.post(
    "/workspaces/{workspace_id}/role-assignments",
    response_model=RoleAssignmentOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a workspace role to a user",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace assignments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks workspace membership management permission.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace, user, or role not found.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid role assignment payload.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Assignment already exists.",
        },
    },
)
async def create_workspace_role_assignment(
    payload: RoleAssignmentCreate,
    workspace_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> RoleAssignmentOut:
    service = RbacService(session=session)
    try:
        assignment = await service.assign_role(
            user_id=payload.user_id,
            role_id=payload.role_id,
            scope_type=ScopeType.WORKSPACE,
            scope_id=workspace_id,
        )
    except (RoleNotFoundError, AssignmentError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _serialize_assignment(assignment)


@router.delete(
    "/workspaces/{workspace_id}/role-assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workspace role assignment",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace assignments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks workspace membership management permission.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role assignment or workspace not found.",
        },
    },
)
async def delete_workspace_role_assignment(
    workspace_id: Annotated[str, Path(..., min_length=1)],
    assignment_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    service = RbacService(session=session)
    try:
        await service.delete_assignment(
            assignment_id=assignment_id,
            scope_type=ScopeType.WORKSPACE,
            scope_id=workspace_id,
        )
    except AssignmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Permission catalog + evaluation
# ---------------------------------------------------------------------------


@router.get(
    "/permissions",
    response_model=PermissionPage,
    summary="List permission catalog entries",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list permissions.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks permission catalog access.",
        },
    },
)
async def list_permissions(
    scope: Annotated[
        ScopeType,
        Query(
            description="Permission scope to list",
            examples={"default": {"value": ScopeType.WORKSPACE.value}},
        ),
    ],
    workspace_id: Annotated[
        str | None,
        Query(
            min_length=1,
            description="Workspace identifier required when scope=workspace.",
        ),
    ] = None,
    *,
    page: Annotated[PageParams, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[
        User,
        Security(
            require_permissions_catalog_access(
                global_permission="roles.read_all",
                workspace_permission="workspace.roles.read",
            ),
            scopes=["{workspace_id}"],
        ),
    ],
) -> PermissionPage:
    if scope == ScopeType.WORKSPACE and workspace_id is not None:
        workspaces = WorkspacesService(session=session)
        await workspaces.get_workspace_profile(user=actor, workspace_id=workspace_id)

    service = RbacService(session=session)
    permissions = await service.list_permissions(scope=scope)
    permission_out = [PermissionOut.model_validate(p) for p in permissions]
    page_result = paginate_sequence(
        permission_out,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return PermissionPage(**page_result.model_dump())


@router.get(
    "/me/permissions",
    response_model=EffectivePermissionsResponse,
    summary="Return the caller's effective permission set",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to inspect permissions.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace access denied for the requested identifier.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found when scoped permissions are requested.",
        },
    },
)
async def read_effective_permissions(
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    workspace_id: Annotated[
        str | None,
        Query(
            min_length=1,
            description="Optional workspace identifier for scoped permissions.",
        ),
    ] = None,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EffectivePermissionsResponse:
    service = RbacService(session=session)

    global_permissions = await service.get_global_permissions_for_user(
        user=identity.user,
    )
    workspace_permissions: frozenset[str] = frozenset()

    if workspace_id is not None:
        workspaces = WorkspacesService(session=session)
        await workspaces.get_workspace_profile(user=identity.user, workspace_id=workspace_id)
        workspace_permissions = await service.get_workspace_permissions_for_user(
            user=identity.user,
            workspace_id=workspace_id,
        )

    return EffectivePermissionsResponse(
        global_permissions=sorted(global_permissions),
        workspace_id=workspace_id,
        workspace_permissions=sorted(workspace_permissions),
    )


@router.post(
    "/me/permissions/check",
    response_model=PermissionCheckResponse,
    summary="Check whether the caller has specific permissions",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to evaluate permissions.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace access denied for the requested identifier.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found when scoped permissions are requested.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid permission keys or missing workspace identifier.",
        },
    },
)
async def check_permissions(
    payload: PermissionCheckRequest,
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PermissionCheckResponse:
    try:
        keys = collect_permission_keys(payload.permissions)
    except AuthorizationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    requires_workspace = any(
        PERMISSION_REGISTRY[key].scope_type == ScopeType.WORKSPACE for key in keys
    )
    workspace_permissions: frozenset[str] = frozenset()
    workspace_id = payload.workspace_id

    if requires_workspace and workspace_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="workspace_id is required when checking workspace permissions",
        )

    service = RbacService(session=session)

    if workspace_id is not None:
        workspaces = WorkspacesService(session=session)
        await workspaces.get_workspace_profile(user=identity.user, workspace_id=workspace_id)
        workspace_permissions = await service.get_workspace_permissions_for_user(
            user=identity.user,
            workspace_id=workspace_id,
        )

    global_permissions = await service.get_global_permissions_for_user(
        user=identity.user,
    )

    results: dict[str, bool] = {}
    for key in keys:
        definition = PERMISSION_REGISTRY[key]
        if definition.scope_type == ScopeType.GLOBAL:
            results[key] = key in global_permissions
        else:
            results[key] = key in workspace_permissions or "workspaces.manage_all" in global_permissions

    return PermissionCheckResponse(results=results)


__all__ = ["router"]
