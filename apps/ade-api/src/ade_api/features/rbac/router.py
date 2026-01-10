from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, Security, status
from ade_api.api.deps import SessionDep
from ade_api.common.concurrency import require_if_match
from ade_api.common.etag import build_etag_token, format_weak_etag
from ade_api.common.list_filters import FilterItem, FilterJoinOperator, FilterOperator
from ade_api.common.listing import ListQueryParams, list_query_params, strict_list_query_guard
from ade_api.common.sorting import resolve_sort
from ade_api.core.auth.principal import AuthenticatedPrincipal
from ade_api.core.http import get_current_principal, require_csrf
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
    WorkspaceMemberOut,
)
from ade_api.features.rbac.service import (
    AssignmentError,
    RbacService,
    RoleConflictError,
    RoleImmutableError,
    RoleNotFoundError,
    RoleValidationError,
    ScopeMismatchError,
    _role_permissions,
)
from ade_api.features.rbac.sorting import (
    ASSIGNMENT_DEFAULT_SORT,
    ASSIGNMENT_ID_FIELD,
    ASSIGNMENT_SORT_FIELDS,
    PERMISSION_DEFAULT_SORT,
    PERMISSION_ID_FIELD,
    PERMISSION_SORT_FIELDS,
)
from ade_api.models import Role, User, UserRoleAssignment

router = APIRouter(tags=["rbac"])

user_roles_router = APIRouter(
    prefix="/users/{userId}/roles",
    tags=["rbac"],
)

PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]
UserPath = Annotated[
    UUID,
    Path(description="User identifier", alias="userId"),
]
RolePath = Annotated[
    UUID,
    Path(description="Role identifier", alias="roleId"),
]
AssignmentPath = Annotated[
    UUID,
    Path(description="Role assignment identifier", alias="assignmentId"),
]


# ---------------------------------------------------------------------------
# Helpers for serialization and permission checks
# ---------------------------------------------------------------------------


def _serialize_role(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        slug=role.slug,
        name=role.name,
        description=role.description,
        permissions=[rp.permission.key for rp in role.permissions if rp.permission is not None],
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
    scope_type = ScopeType.WORKSPACE if assignment.workspace_id else ScopeType.GLOBAL
    return RoleAssignmentOut(
        id=assignment.id,
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        role_slug=assignment.role.slug if assignment.role is not None else "",
        scope_type=scope_type,
        scope_id=assignment.workspace_id,
        created_at=assignment.created_at,
    )


def _serialize_member(assignments: Iterable[UserRoleAssignment]) -> WorkspaceMemberOut:
    assignments = list(assignments)
    if not assignments:
        raise ValueError("workspace member requires at least one assignment")
    user_id = assignments[0].user_id
    role_ids = [assignment.role_id for assignment in assignments]
    role_slugs = [
        assignment.role.slug if assignment.role is not None else "" for assignment in assignments
    ]
    created_at = min(assignment.created_at for assignment in assignments)
    return WorkspaceMemberOut(
        user_id=user_id,
        role_ids=role_ids,
        role_slugs=role_slugs,
        created_at=created_at,
    )


def _ensure_global_permission(
    *,
    service: RbacService,
    principal: AuthenticatedPrincipal,
    permission_key: str,
) -> None:
    ok = service.has_permission_for_user_id(
        user_id=principal.user_id,
        permission_key=permission_key,
        workspace_id=None,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


def _ensure_workspace_permission(
    *,
    service: RbacService,
    principal: AuthenticatedPrincipal,
    permission_key: str,
    workspace_id: UUID,
) -> None:
    ok = service.has_permission_for_user_id(
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
def list_permissions(
    principal: PrincipalDep,
    session: SessionDep,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    _guard: Annotated[None, Depends(strict_list_query_guard())],
) -> PermissionPage:
    service = RbacService(session=session)
    # Require ability to read roles/permissions
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    order_by = resolve_sort(
        list_query.sort,
        allowed=PERMISSION_SORT_FIELDS,
        default=PERMISSION_DEFAULT_SORT,
        id_field=PERMISSION_ID_FIELD,
    )
    page_result = service.list_permissions(
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        order_by=order_by,
        page=list_query.page,
        per_page=list_query.per_page,
    )
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
        for permission in page_result.items
    ]
    return PermissionPage(
        items=items,
        page=page_result.page,
        per_page=page_result.per_page,
        page_count=page_result.page_count,
        total=page_result.total,
        changes_cursor=page_result.changes_cursor,
    )


# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------


@router.get(
    "/roles",
    response_model=RolePage,
    response_model_exclude_none=True,
    summary="List role definitions",
)
def list_roles(
    principal: PrincipalDep,
    session: SessionDep,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    _guard: Annotated[None, Depends(strict_list_query_guard())],
) -> RolePage:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    role_page = service.list_roles(
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        sort=list_query.sort,
        page=list_query.page,
        per_page=list_query.per_page,
    )
    return RolePage(
        items=[_serialize_role(role) for role in role_page.items],
        page=role_page.page,
        per_page=role_page.per_page,
        page_count=role_page.page_count,
        total=role_page.total,
        changes_cursor=role_page.changes_cursor,
    )


@router.post(
    "/roles",
    dependencies=[Security(require_csrf)],
    response_model=RoleOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create a role",
)
def create_role(
    payload: RoleCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> RoleOut:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    actor = session.get(User, principal.user_id)
    try:
        role = service.create_role(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            permissions=payload.permissions,
            actor=actor,
        )
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _serialize_role(role)


def _load_role(
    role_id: RolePath,
    session: SessionDep,
) -> Role:
    service = RbacService(session=session)
    role = service.get_role(role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.get(
    "/roles/{roleId}",
    response_model=RoleOut,
    response_model_exclude_none=True,
    summary="Retrieve a role definition",
)
def read_role(
    role: Annotated[Role, Depends(_load_role)],
    principal: PrincipalDep,
    session: SessionDep,
    response: Response,
) -> RoleOut:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )
    payload = _serialize_role(role)
    etag = format_weak_etag(build_etag_token(role.id, role.updated_at or role.created_at))
    if etag:
        response.headers["ETag"] = etag
    return payload


@router.patch(
    "/roles/{roleId}",
    dependencies=[Security(require_csrf)],
    response_model=RoleOut,
    response_model_exclude_none=True,
    summary="Update an existing role",
)
def update_role(
    payload: RoleUpdate,
    role: Annotated[Role, Depends(_load_role)],
    principal: PrincipalDep,
    session: SessionDep,
    request: Request,
    response: Response,
) -> RoleOut:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    actor = session.get(User, principal.user_id)
    require_if_match(
        request.headers.get("if-match"),
        expected_token=build_etag_token(role.id, role.updated_at or role.created_at),
    )

    try:
        updated = service.update_role(
            role_id=role.id,
            name=payload.name or role.name,
            description=(
                payload.description if payload.description is not None else role.description
            ),
            permissions=payload.permissions or _role_permissions(role),
            actor=actor,
        )
    except RoleImmutableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoleValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    payload = _serialize_role(updated)
    etag = format_weak_etag(build_etag_token(updated.id, updated.updated_at or updated.created_at))
    if etag:
        response.headers["ETag"] = etag
    return payload


@router.delete(
    "/roles/{roleId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a role",
)
def delete_role(
    role: Annotated[Role, Depends(_load_role)],
    principal: PrincipalDep,
    session: SessionDep,
    request: Request,
) -> Response:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    try:
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(role.id, role.updated_at or role.created_at),
        )
        service.delete_role(role_id=role.id)
    except RoleImmutableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RoleConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Admin assignments listing (optional)
# ---------------------------------------------------------------------------


@router.get(
    "/roleassignments",
    response_model=RoleAssignmentPage,
    response_model_exclude_none=True,
    summary="List role assignments (admin view)",
)
def list_assignments(
    principal: PrincipalDep,
    session: SessionDep,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    _guard: Annotated[None, Depends(strict_list_query_guard())],
) -> RoleAssignmentPage:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    order_by = resolve_sort(
        list_query.sort,
        allowed=ASSIGNMENT_SORT_FIELDS,
        default=ASSIGNMENT_DEFAULT_SORT,
        id_field=ASSIGNMENT_ID_FIELD,
    )
    assignments = service.list_assignments(
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        order_by=order_by,
        page=list_query.page,
        per_page=list_query.per_page,
    )
    return RoleAssignmentPage(
        items=[_serialize_assignment(item) for item in assignments.items],
        page=assignments.page,
        per_page=assignments.per_page,
        page_count=assignments.page_count,
        total=assignments.total,
        changes_cursor=assignments.changes_cursor,
    )


@router.get(
    "/roleassignments/{assignmentId}",
    response_model=RoleAssignmentOut,
    response_model_exclude_none=True,
    summary="Retrieve a role assignment",
)
def read_assignment(
    assignment_id: AssignmentPath,
    principal: PrincipalDep,
    session: SessionDep,
    response: Response,
) -> RoleAssignmentOut:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    assignment = service.get_assignment(assignment_id=assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role assignment not found")

    payload = _serialize_assignment(assignment)
    etag = format_weak_etag(build_etag_token(assignment.id, assignment.created_at))
    if etag:
        response.headers["ETag"] = etag
    return payload


# ---------------------------------------------------------------------------
# Global role assignments per user
# ---------------------------------------------------------------------------


def _load_user_role_assignments(
    *,
    service: RbacService,
    user_id: UUID,
) -> list[UserRoleAssignment]:
    order_by = resolve_sort(
        [],
        allowed=ASSIGNMENT_SORT_FIELDS,
        default=ASSIGNMENT_DEFAULT_SORT,
        id_field=ASSIGNMENT_ID_FIELD,
    )
    assignments_page = service.list_assignments(
        filters=[
            FilterItem(id="userId", operator=FilterOperator.EQ, value=str(user_id)),
            FilterItem(id="scopeId", operator=FilterOperator.IS_EMPTY, value=None),
        ],
        join_operator=FilterJoinOperator.AND,
        q=None,
        order_by=order_by,
        page=1,
        per_page=1000,
        default_active_only=False,
    )
    return assignments_page.items


@user_roles_router.get(
    "",
    response_model=UserRolesEnvelope,
    summary="List global roles assigned to a user",
)
def list_user_roles(
    user_id: UserPath,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserRolesEnvelope:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    assignments = _load_user_role_assignments(service=service, user_id=user_id)
    return UserRolesEnvelope(
        user_id=user_id,
        roles=[_serialize_user_role(assignment) for assignment in assignments],
    )


@user_roles_router.put(
    "/{roleId}",
    dependencies=[Security(require_csrf)],
    response_model=UserRolesEnvelope,
    summary="Assign a global role to a user (idempotent)",
)
def assign_user_role(
    user_id: UserPath,
    role_id: RolePath,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserRolesEnvelope:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    try:
        service.assign_role_if_missing(
            user_id=user_id,
            role_id=role_id,
            workspace_id=None,
        )
    except (RoleNotFoundError, AssignmentError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    assignments = _load_user_role_assignments(service=service, user_id=user_id)
    return UserRolesEnvelope(
        user_id=user_id,
        roles=[_serialize_user_role(assignment) for assignment in assignments],
    )


@user_roles_router.delete(
    "/{roleId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a global role from a user",
)
def remove_user_role(
    user_id: UserPath,
    role_id: RolePath,
    principal: PrincipalDep,
    session: SessionDep,
    request: Request,
) -> Response:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    assignment = service.get_assignment_for_user_role(
        user_id=user_id,
        role_id=role_id,
        workspace_id=None,
    )
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role assignment not found")

    try:
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(assignment.id, assignment.created_at),
        )
        service.delete_assignment(
            assignment_id=assignment.id,
            workspace_id=None,
        )
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router", "user_roles_router"]
