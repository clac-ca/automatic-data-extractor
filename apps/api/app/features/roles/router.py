"""HTTP endpoints for role and permission management."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.shared.core.security import forbidden_response
from apps.api.app.shared.db.session import get_session
from apps.api.app.shared.dependency import (
    get_current_identity,
    require_authenticated,
    require_csrf,
    require_global,
    require_permissions_catalog_access,
    require_workspace,
)
from apps.api.app.shared.pagination import PageParams, paginate_sequence

from ..auth.service import AuthenticatedIdentity
from ..users.models import User
from ..workspaces.service import WorkspacesService
from .authorization import authorize
from .models import (
    Permission,
    Principal,
    PrincipalType,
    Role,
    RoleAssignment,
    ScopeType,
)
from .registry import PERMISSION_REGISTRY, PermissionScope
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
    AuthorizationError,
    PrincipalNotFoundError,
    RoleAssignmentError,
    RoleAssignmentNotFoundError,
    RoleConflictError,
    RoleImmutableError,
    RoleNotFoundError,
    RoleScopeMismatchError,
    RoleValidationError,
    WorkspaceNotFoundError,
    assign_role,
    collect_permission_keys,
    create_global_role,
    delete_global_role,
    delete_role_assignment,
    ensure_user_principal,
    get_global_permissions_for_principal,
    get_role,
    get_role_assignment,
    get_workspace_permissions_for_principal,
    paginate_role_assignments,
    paginate_roles,
    update_global_role,
)

router = APIRouter(tags=["roles"], dependencies=[Security(require_authenticated)])


def _serialize_role(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        slug=role.slug,
        name=role.name,
        description=role.description,
        scope_type=role.scope_type,
        scope_id=role.scope_id,
        permissions=[
            permission.permission.key
            for permission in role.permissions
            if permission.permission is not None
        ],
        built_in=role.built_in,
        editable=role.editable,
    )


def _serialize_assignment(assignment: RoleAssignment) -> RoleAssignmentOut:
    principal = assignment.principal
    user = principal.user if principal is not None else None
    return RoleAssignmentOut(
        id=assignment.id,
        principal_id=assignment.principal_id,
        principal_type=(
            principal.principal_type if principal is not None else PrincipalType.USER
        ),
        user_id=user.id if user is not None else None,
        user_email=user.email if user is not None else None,
        user_display_name=user.display_name if user is not None else None,
        role_id=assignment.role_id,
        role_slug=assignment.role.slug if assignment.role is not None else "",
        scope_type=assignment.scope_type,
        scope_id=assignment.scope_id,
        created_at=assignment.created_at,
    )


async def _ensure_principal_identifier(
    *,
    session: AsyncSession,
    principal_id: str | None,
    user_id: str | None,
) -> str:
    if principal_id:
        result = await session.execute(
            select(Principal.id).where(Principal.id == principal_id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Principal not found")
        return principal_id

    if user_id:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
        principal = await ensure_user_principal(session=session, user=user)
        return cast(str, principal.id)

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="principal_id or user_id is required",
    )


async def _resolve_principal_filter(
    *,
    session: AsyncSession,
    principal_id: str | None,
    user_id: str | None,
) -> str | None:
    if principal_id:
        return principal_id

    if user_id:
        result = await session.execute(
            select(Principal.id).where(Principal.user_id == user_id)
        )
        principal = result.scalar_one_or_none()
        return principal

    return None


def _role_permission_requirements(role: Role, *, write: bool) -> tuple[str, str, str | None]:
    if role.scope_type == ScopeType.GLOBAL:
        permission = "Roles.ReadWrite.All" if write else "Roles.Read.All"
        return permission, ScopeType.GLOBAL, None

    if role.scope_id is None:
        permission = "Roles.ReadWrite.All" if write else "Roles.Read.All"
        return permission, ScopeType.GLOBAL, None

    permission = "Workspace.Roles.ReadWrite" if write else "Workspace.Roles.Read"
    return permission, ScopeType.WORKSPACE, role.scope_id


async def _load_role(
    role_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Role:
    role = await get_role(session=session, role_id=role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


async def require_role_read_access(
    role: Annotated[Role, Depends(_load_role)],
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Role:
    if identity.credentials == "development":
        return role
    permission, scope_type, scope_id = _role_permission_requirements(role, write=False)
    decision = await authorize(
        session=session,
        principal_id=str(identity.principal.id),
        permission_key=permission,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    if not decision.is_authorized:
        raise forbidden_response(
            permission=permission,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    return role


async def require_role_write_access(
    role: Annotated[Role, Depends(_load_role)],
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> tuple[User, Role]:
    if identity.credentials == "development":
        return identity.user, role
    permission, scope_type, scope_id = _role_permission_requirements(role, write=True)
    decision = await authorize(
        session=session,
        principal_id=str(identity.principal.id),
        permission_key=permission,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    if not decision.is_authorized:
        raise forbidden_response(
            permission=permission,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    return identity.user, role


@router.get(
    "/roles",
    response_model=RolePage,
    response_model_exclude_none=True,
    summary="List global role definitions",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks global role read permission.",
        },
    },
)
async def list_global_roles(
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: Annotated[
        ScopeType,
        Query(
            description="Role scope to list (global only)",
            alias="scope",
        ),
    ] = ScopeType.GLOBAL,
    page: Annotated[PageParams, Depends()],
    _actor: Annotated[User, Security(require_global("Roles.Read.All"))],
) -> RolePage:
    """Return the catalog of global roles."""

    role_page = await paginate_roles(
        session=session,
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
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
    summary="Create a global role",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks global role management permission.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Role slug already exists.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Role payload is invalid.",
        },
    },
)
async def create_global_role_endpoint(
    payload: RoleCreate,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: Annotated[
        ScopeType,
        Query(
            description="Role scope to create (global only)",
            alias="scope",
        ),
    ] = ScopeType.GLOBAL,
    actor: Annotated[User, Security(require_global("Roles.ReadWrite.All"))],
) -> RoleOut:
    """Create a new global role definition."""

    try:
        role = await create_global_role(
            session=session, payload=payload, actor=actor
        )
    except RoleConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RoleValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return _serialize_role(role)


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
async def read_role_detail(
    role: Annotated[Role, Security(require_role_read_access)],
    role_id: str = Path(..., min_length=1),
) -> RoleOut:
    """Return a single role definition with permissions."""

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
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Role payload is invalid.",
        },
    },
)
async def update_role_definition(
    payload: RoleUpdate,
    actor_and_role: Annotated[tuple[User, Role], Security(require_role_write_access)],
    role_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RoleOut:
    """Update the specified role in its scope."""

    actor, role = actor_and_role

    if role.scope_type == ScopeType.GLOBAL:
        try:
            updated = await update_global_role(
                session=session, role_id=role_id, payload=payload, actor=actor
            )
        except RoleImmutableError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RoleValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except RoleNotFoundError:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            ) from None

        return _serialize_role(updated)

    if role.scope_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be edited",
        )

    workspaces = WorkspacesService(session=session)
    updated = await workspaces.update_workspace_role(
        workspace_id=role.scope_id,
        role_id=role_id,
        payload=payload,
        actor=actor,
    )
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
            "description": "Role is still assigned to principals.",
        },
    },
)
async def delete_role_definition(
    actor_and_role: Annotated[tuple[User, Role], Security(require_role_write_access)],
    role_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete the specified role definition."""

    _actor, role = actor_and_role

    if role.scope_type == ScopeType.GLOBAL:
        try:
            await delete_global_role(session=session, role_id=role_id)
        except RoleImmutableError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RoleConflictError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except RoleNotFoundError:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            ) from None

        return

    if role.scope_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be deleted",
        )

    workspaces = WorkspacesService(session=session)
    await workspaces.delete_workspace_role(
        workspace_id=role.scope_id,
        role_id=role_id,
    )


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
    principal_id: Annotated[str | None, Query(min_length=1)] = None,
    user_id: Annotated[str | None, Query(min_length=1)] = None,
    role_id: Annotated[str | None, Query(min_length=1)] = None,
    page: Annotated[PageParams, Depends()],
    _actor: Annotated[User, Security(require_global("Roles.Read.All"))],
) -> RoleAssignmentPage:
    """Return global role assignments filtered by optional identifiers."""

    if principal_id and user_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide only one of principal_id or user_id",
        )

    principal_filter = await _resolve_principal_filter(
        session=session, principal_id=principal_id, user_id=user_id
    )

    if user_id and principal_filter is None:
        total = 0 if page.include_total else None
        return RoleAssignmentPage(
            items=[],
            page=page.page,
            page_size=page.page_size,
            has_next=False,
            has_previous=page.page > 1,
            total=total,
        )

    assignments_page = await paginate_role_assignments(
        session=session,
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
        principal_id=principal_filter,
        role_id=role_id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return RoleAssignmentPage(
        items=[_serialize_assignment(assignment) for assignment in assignments_page.items],
        page=assignments_page.page,
        page_size=assignments_page.page_size,
        has_next=assignments_page.has_next,
        has_previous=assignments_page.has_previous,
        total=assignments_page.total,
    )


@router.post(
    "/role-assignments",
    response_model=RoleAssignmentOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Assign a global role to a principal",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage role assignments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks global role assignment permission.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Principal or role not found.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Invalid role assignment payload.",
        },
    },
)
async def create_global_role_assignment(
    payload: RoleAssignmentCreate,
    response: Response,
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[User, Security(require_global("Roles.ReadWrite.All"))],
) -> RoleAssignmentOut:
    """Create or return an existing global role assignment."""

    principal_identifier = await _ensure_principal_identifier(
        session=session,
        principal_id=payload.principal_id,
        user_id=payload.user_id,
    )

    existing = await get_role_assignment(
        session=session,
        principal_id=principal_identifier,
        role_id=payload.role_id,
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
    )
    if existing is not None:
        return _serialize_assignment(existing)

    try:
        await assign_role(
            session=session,
            principal_id=principal_identifier,
            role_id=payload.role_id,
            scope_type=ScopeType.GLOBAL,
            scope_id=None,
        )
    except (PrincipalNotFoundError, RoleNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RoleAssignmentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    assignment = await get_role_assignment(
        session=session,
        principal_id=principal_identifier,
        role_id=payload.role_id,
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
    )
    if assignment is None:  # pragma: no cover - defensive guard
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role assignment could not be created",
        )

    response.status_code = status.HTTP_201_CREATED
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
    _actor: Annotated[User, Security(require_global("Roles.ReadWrite.All"))],
) -> None:
    """Delete a global role assignment by identifier."""

    try:
        await delete_role_assignment(
            session=session,
            assignment_id=assignment_id,
            scope_type=ScopeType.GLOBAL,
            scope_id=None,
        )
    except RoleAssignmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
    principal_id: Annotated[str | None, Query(min_length=1)] = None,
    user_id: Annotated[str | None, Query(min_length=1)] = None,
    role_id: Annotated[str | None, Query(min_length=1)] = None,
    *,
    page: Annotated[PageParams, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Members.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> RoleAssignmentPage:
    """Return workspace role assignments filtered by optional identifiers."""

    if principal_id and user_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide only one of principal_id or user_id",
        )

    principal_filter = await _resolve_principal_filter(
        session=session, principal_id=principal_id, user_id=user_id
    )

    if user_id and principal_filter is None:
        total = 0 if page.include_total else None
        return RoleAssignmentPage(
            items=[],
            page=page.page,
            page_size=page.page_size,
            has_next=False,
            has_previous=page.page > 1,
            total=total,
        )

    assignments_page = await paginate_role_assignments(
        session=session,
        scope_type=ScopeType.WORKSPACE,
        scope_id=workspace_id,
        principal_id=principal_filter,
        role_id=role_id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return RoleAssignmentPage(
        items=[_serialize_assignment(assignment) for assignment in assignments_page.items],
        page=assignments_page.page,
        page_size=assignments_page.page_size,
        has_next=assignments_page.has_next,
        has_previous=assignments_page.has_previous,
        total=assignments_page.total,
    )


@router.post(
    "/workspaces/{workspace_id}/role-assignments",
    response_model=RoleAssignmentOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Assign a workspace role to a principal",
    dependencies=[Security(require_csrf)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace assignments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks workspace membership management permission.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace, principal, or role not found.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Invalid role assignment payload.",
        },
    },
)
async def create_workspace_role_assignment(
    payload: RoleAssignmentCreate,
    response: Response,
    workspace_id: Annotated[str, Path(..., min_length=1)],
    *,
    session: Annotated[AsyncSession, Depends(get_session)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Members.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> RoleAssignmentOut:
    """Create or return an existing workspace role assignment."""

    principal_identifier = await _ensure_principal_identifier(
        session=session,
        principal_id=payload.principal_id,
        user_id=payload.user_id,
    )

    existing = await get_role_assignment(
        session=session,
        principal_id=principal_identifier,
        role_id=payload.role_id,
        scope_type=ScopeType.WORKSPACE,
        scope_id=workspace_id,
    )
    if existing is not None:
        return _serialize_assignment(existing)

    try:
        await assign_role(
            session=session,
            principal_id=principal_identifier,
            role_id=payload.role_id,
            scope_type=ScopeType.WORKSPACE,
            scope_id=workspace_id,
        )
    except (PrincipalNotFoundError, RoleNotFoundError, WorkspaceNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleScopeMismatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RoleAssignmentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    assignment = await get_role_assignment(
        session=session,
        principal_id=principal_identifier,
        role_id=payload.role_id,
        scope_type=ScopeType.WORKSPACE,
        scope_id=workspace_id,
    )
    if assignment is None:  # pragma: no cover - defensive guard
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role assignment could not be created",
        )

    response.status_code = status.HTTP_201_CREATED
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
            require_workspace("Workspace.Members.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> None:
    """Delete a workspace role assignment by identifier."""

    try:
        await delete_role_assignment(
            session=session,
            assignment_id=assignment_id,
            scope_type=ScopeType.WORKSPACE,
            scope_id=workspace_id,
        )
    except RoleAssignmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
        PermissionScope,
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
                global_permission="Roles.Read.All",
                workspace_permission="Workspace.Roles.Read",
            ),
            scopes=["{workspace_id}"],
        ),
    ],
) -> PermissionPage:
    """Return permission registry entries filtered by ``scope``."""

    if scope == ScopeType.WORKSPACE and workspace_id is not None:
        service = WorkspacesService(session=session)
        await service.get_workspace_profile(user=actor, workspace_id=workspace_id)

    stmt = (
        select(Permission)
        .where(Permission.scope_type == scope)
        .order_by(Permission.key)
    )
    result = await session.execute(stmt)
    permissions = [PermissionOut.model_validate(p) for p in result.scalars().all()]
    page_result = paginate_sequence(
        permissions,
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
    """Return global and optional workspace permissions for the active user."""

    user = identity.user
    principal = identity.principal

    global_permissions = await get_global_permissions_for_principal(
        session=session,
        principal=principal,
    )
    workspace_permissions: frozenset[str] = frozenset()

    if workspace_id is not None:
        workspaces = WorkspacesService(session=session)
        await workspaces.get_workspace_profile(user=user, workspace_id=workspace_id)
        workspace_permissions = await get_workspace_permissions_for_principal(
            session=session,
            principal=principal,
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
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Invalid permission keys or missing workspace identifier.",
        },
    },
)
async def check_permissions(
    payload: PermissionCheckRequest,
    identity: Annotated[AuthenticatedIdentity, Depends(get_current_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PermissionCheckResponse:
    """Return a permission map describing whether the caller has each key."""

    try:
        keys = collect_permission_keys(payload.permissions)
    except AuthorizationError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    requires_workspace = any(
        PERMISSION_REGISTRY[key].scope == ScopeType.WORKSPACE for key in keys
    )
    workspace_permissions: frozenset[str] = frozenset()
    workspace_id = payload.workspace_id

    if requires_workspace and workspace_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="workspace_id is required when checking workspace permissions",
        )

    user = identity.user
    principal = identity.principal

    if workspace_id is not None:
        workspaces = WorkspacesService(session=session)
        await workspaces.get_workspace_profile(user=user, workspace_id=workspace_id)
        workspace_permissions = await get_workspace_permissions_for_principal(
            session=session,
            principal=principal,
            workspace_id=workspace_id,
        )

    global_permissions = await get_global_permissions_for_principal(
        session=session,
        principal=principal,
    )

    results: dict[str, bool] = {}
    for key in keys:
        definition = PERMISSION_REGISTRY[key]
        if definition.scope == ScopeType.GLOBAL:
            results[key] = key in global_permissions
        else:
            results[key] = key in workspace_permissions

    return PermissionCheckResponse(results=results)


__all__ = ["router"]
