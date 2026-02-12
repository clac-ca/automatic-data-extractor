from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, Security, status

from ade_api.api.deps import ReadSessionDep, WriteSessionDep
from ade_api.common.concurrency import require_if_match
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort,
    resolve_cursor_sort_sequence,
    strict_cursor_query_guard,
)
from ade_api.common.etag import build_etag_token, format_weak_etag
from ade_api.core.auth.principal import AuthenticatedPrincipal
from ade_api.core.http import get_current_principal, require_csrf, require_workspace
from ade_api.features.rbac.schemas import (
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
from ade_api.features.rbac.sorting import (
    PERMISSION_CURSOR_FIELDS,
    PERMISSION_DEFAULT_SORT,
    PERMISSION_ID_FIELD,
    PERMISSION_SORT_FIELDS,
    PRINCIPAL_ASSIGNMENT_CURSOR_FIELDS,
    PRINCIPAL_ASSIGNMENT_DEFAULT_SORT,
    PRINCIPAL_ASSIGNMENT_ID_FIELD,
    PRINCIPAL_ASSIGNMENT_SORT_FIELDS,
    ROLE_CURSOR_FIELDS,
    ROLE_DEFAULT_SORT,
    PrincipalAssignmentRow,
)
from ade_db.models import AssignmentScopeType, Role, RoleAssignment, User

router = APIRouter(tags=["rbac"])

PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_current_principal)]
WorkspacePath = Annotated[
    UUID,
    Path(description="Workspace identifier", alias="workspaceId"),
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
# Helpers
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


def _serialize_assignment(service: RbacService, assignment: RoleAssignment) -> RoleAssignmentOut:
    role = service.get_role(assignment.role_id)
    role_slug = role.slug if role is not None else ""
    principal_display_name, principal_email, principal_slug = service.get_principal_identity(
        principal_type=assignment.principal_type,
        principal_id=assignment.principal_id,
    )
    return RoleAssignmentOut(
        id=assignment.id,
        principal_type=assignment.principal_type,
        principal_id=assignment.principal_id,
        principal_display_name=principal_display_name,
        principal_email=principal_email,
        principal_slug=principal_slug,
        role_id=assignment.role_id,
        role_slug=role_slug,
        scope_type=assignment.scope_type,
        scope_id=assignment.scope_id,
        created_at=assignment.created_at,
    )


def _serialize_principal_assignment_row(item: PrincipalAssignmentRow) -> RoleAssignmentOut:
    return RoleAssignmentOut(
        id=item.id,
        principal_type=item.principal_type,
        principal_id=item.principal_id,
        principal_display_name=item.principal_display_name,
        principal_email=item.principal_email,
        principal_slug=item.principal_slug,
        role_id=item.role_id,
        role_slug=item.role_slug,
        scope_type=item.scope_type,
        scope_id=item.scope_id,
        created_at=item.created_at,
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


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
    session: ReadSessionDep,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
) -> PermissionPage:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=PERMISSION_SORT_FIELDS,
        cursor_fields=PERMISSION_CURSOR_FIELDS,
        default=PERMISSION_DEFAULT_SORT,
        id_field=PERMISSION_ID_FIELD,
    )
    page_result = service.list_permissions(
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        resolved_sort=resolved_sort,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
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
    return PermissionPage(items=items, meta=page_result.meta, facets=page_result.facets)


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
    session: ReadSessionDep,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
) -> RolePage:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )

    resolved_sort = resolve_cursor_sort_sequence(
        list_query.sort,
        cursor_fields=ROLE_CURSOR_FIELDS,
        default=ROLE_DEFAULT_SORT,
    )
    role_page = service.list_roles(
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        resolved_sort=resolved_sort,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )
    return RolePage(
        items=[_serialize_role(role) for role in role_page.items],
        meta=role_page.meta,
        facets=role_page.facets,
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
    session: WriteSessionDep,
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
    session: WriteSessionDep,
) -> Role:
    service = RbacService(session=session)
    role = service.get_role(role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


def _load_role_readonly(
    role_id: RolePath,
    session: ReadSessionDep,
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
    role: Annotated[Role, Depends(_load_role_readonly)],
    principal: PrincipalDep,
    session: ReadSessionDep,
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
    session: WriteSessionDep,
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

    response_payload = _serialize_role(updated)
    etag = format_weak_etag(build_etag_token(updated.id, updated.updated_at or updated.created_at))
    if etag:
        response.headers["ETag"] = etag
    return response_payload


@router.delete(
    "/roles/{roleId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a role",
)
def delete_role(
    role: Annotated[Role, Depends(_load_role)],
    principal: PrincipalDep,
    session: WriteSessionDep,
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
# Principal-aware role assignments
# ---------------------------------------------------------------------------


@router.get(
    "/roleAssignments",
    response_model=RoleAssignmentPage,
    response_model_exclude_none=True,
    summary="List organization role assignments",
)
def list_organization_role_assignments(
    principal: PrincipalDep,
    session: ReadSessionDep,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
) -> RoleAssignmentPage:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.read_all",
    )
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=PRINCIPAL_ASSIGNMENT_SORT_FIELDS,
        cursor_fields=PRINCIPAL_ASSIGNMENT_CURSOR_FIELDS,
        default=PRINCIPAL_ASSIGNMENT_DEFAULT_SORT,
        id_field=PRINCIPAL_ASSIGNMENT_ID_FIELD,
    )
    assignments = service.list_principal_assignments(
        scope_type=AssignmentScopeType.ORGANIZATION,
        scope_id=None,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        resolved_sort=resolved_sort,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )
    return RoleAssignmentPage(
        items=[_serialize_principal_assignment_row(item) for item in assignments.items],
        meta=assignments.meta,
        facets=assignments.facets,
    )


@router.post(
    "/roleAssignments",
    dependencies=[Security(require_csrf)],
    response_model=RoleAssignmentOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization role assignment",
)
def create_organization_role_assignment(
    payload: RoleAssignmentCreate,
    principal: PrincipalDep,
    session: WriteSessionDep,
) -> RoleAssignmentOut:
    service = RbacService(session=session)
    _ensure_global_permission(
        service=service,
        principal=principal,
        permission_key="roles.manage_all",
    )

    try:
        assignment = service.assign_principal_role_if_missing(
            principal_type=payload.principal_type,
            principal_id=payload.principal_id,
            role_id=payload.role_id,
            scope_type=AssignmentScopeType.ORGANIZATION,
            scope_id=None,
        )
    except (RoleNotFoundError, AssignmentError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _serialize_assignment(service, assignment)


@router.get(
    "/workspaces/{workspaceId}/roleAssignments",
    response_model=RoleAssignmentPage,
    response_model_exclude_none=True,
    summary="List workspace role assignments",
)
def list_workspace_role_assignments(
    workspace_id: WorkspacePath,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
    session: ReadSessionDep,
    _actor: Annotated[
        User,
        Security(require_workspace("workspace.members.read"), scopes=["{workspaceId}"]),
    ],
) -> RoleAssignmentPage:
    service = RbacService(session=session)
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=PRINCIPAL_ASSIGNMENT_SORT_FIELDS,
        cursor_fields=PRINCIPAL_ASSIGNMENT_CURSOR_FIELDS,
        default=PRINCIPAL_ASSIGNMENT_DEFAULT_SORT,
        id_field=PRINCIPAL_ASSIGNMENT_ID_FIELD,
    )
    assignments = service.list_principal_assignments(
        scope_type=AssignmentScopeType.WORKSPACE,
        scope_id=workspace_id,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        resolved_sort=resolved_sort,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )
    return RoleAssignmentPage(
        items=[_serialize_principal_assignment_row(item) for item in assignments.items],
        meta=assignments.meta,
        facets=assignments.facets,
    )


@router.post(
    "/workspaces/{workspaceId}/roleAssignments",
    dependencies=[Security(require_csrf)],
    response_model=RoleAssignmentOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace role assignment",
)
def create_workspace_role_assignment(
    workspace_id: WorkspacePath,
    payload: RoleAssignmentCreate,
    _actor: Annotated[
        User,
        Security(require_workspace("workspace.members.manage"), scopes=["{workspaceId}"]),
    ],
    session: WriteSessionDep,
) -> RoleAssignmentOut:
    service = RbacService(session=session)
    try:
        assignment = service.assign_principal_role_if_missing(
            principal_type=payload.principal_type,
            principal_id=payload.principal_id,
            role_id=payload.role_id,
            scope_type=AssignmentScopeType.WORKSPACE,
            scope_id=workspace_id,
        )
    except (RoleNotFoundError, AssignmentError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return _serialize_assignment(service, assignment)


@router.delete(
    "/roleAssignments/{assignmentId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a principal role assignment",
)
def delete_role_assignment(
    assignment_id: AssignmentPath,
    principal: PrincipalDep,
    session: WriteSessionDep,
) -> Response:
    service = RbacService(session=session)
    assignment = service.get_principal_assignment(assignment_id=assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role assignment not found")

    if assignment.scope_type == AssignmentScopeType.ORGANIZATION:
        _ensure_global_permission(
            service=service,
            principal=principal,
            permission_key="roles.manage_all",
        )
    elif assignment.scope_id is None or not service.has_permission_for_user_id(
        user_id=principal.user_id,
        permission_key="workspace.members.manage",
        workspace_id=assignment.scope_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        service.delete_principal_assignment(assignment_id=assignment_id)
    except AssignmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
