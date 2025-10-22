"""Service functions for ADE's unified RBAC implementation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable, Mapping, Sequence, cast

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.features.users.models import User
from backend.app.features.workspaces.models import Workspace

from .models import Permission, Principal, Role, RoleAssignment, RolePermission
from .registry import (
    PERMISSIONS,
    PERMISSION_REGISTRY,
    PermissionScope,
    SYSTEM_ROLES,
)


GLOBAL_IMPLICATIONS: Mapping[str, tuple[str, ...]] = {
    "Roles.ReadWrite.All": ("Roles.Read.All",),
    "System.Settings.ReadWrite": ("System.Settings.Read",),
    "Workspaces.ReadWrite.All": ("Workspaces.Read.All",),
}


WORKSPACE_IMPLICATIONS: Mapping[str, tuple[str, ...]] = {}


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class AuthorizationError(ValueError):
    """Raised when permission inputs are invalid or unregistered."""


class RoleError(ValueError):
    """Base class for role management errors."""


class RoleValidationError(RoleError):
    """Raised when role payload data is invalid."""


class RoleConflictError(RoleError):
    """Raised when a role operation would violate uniqueness constraints."""


class RoleImmutableError(RoleError):
    """Raised when attempting to mutate a system or non-editable role."""


class RoleNotFoundError(RoleError):
    """Raised when a role cannot be located for the requested operation."""


class RoleAssignmentError(ValueError):
    """Base class for role assignment errors."""


class PrincipalNotFoundError(RoleAssignmentError):
    """Raised when the requested principal does not exist."""


class WorkspaceNotFoundError(RoleAssignmentError):
    """Raised when the requested workspace scope cannot be resolved."""


class RoleScopeMismatchError(RoleAssignmentError):
    """Raised when a role cannot be applied to the requested scope."""


class RoleAssignmentNotFoundError(RoleAssignmentError):
    """Raised when a role assignment cannot be located."""


@dataclass(frozen=True)
class AuthorizationDecision:
    """Represents the outcome of an authorization evaluation."""

    granted: frozenset[str]
    required: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def is_authorized(self) -> bool:
        return not self.missing


def _coerce_identifier(candidate: str | Enum) -> str:
    if isinstance(candidate, Enum):
        value = str(candidate.value)
    else:
        value = str(candidate)
    normalized = value.strip()
    if not normalized:
        msg = "Permission identifiers cannot be blank"
        raise AuthorizationError(msg)
    return normalized


def collect_permission_keys(permissions: Iterable[str | Enum]) -> tuple[str, ...]:
    """Normalize the supplied ``permissions`` into registered Graph-style keys."""

    collected: list[str] = []
    for identifier in permissions:
        key = _coerce_identifier(identifier)
        if key not in PERMISSION_REGISTRY:
            msg = f"Permission '{key}' is not registered"
            raise AuthorizationError(msg)
        collected.append(key)
    return tuple(collected)


def _validate_scope(keys: Sequence[str], *, scope: PermissionScope) -> None:
    for key in keys:
        definition = PERMISSION_REGISTRY.get(key)
        if definition is None:
            msg = f"Permission '{key}' is not registered"
            raise AuthorizationError(msg)
        if definition.scope != scope:
            msg = f"Permission '{key}' is not {scope}-scoped"
            raise AuthorizationError(msg)


def _expand_implications(keys: frozenset[str], *, scope: PermissionScope) -> frozenset[str]:
    """Expand ``keys`` using the configured implication mappings."""

    if not keys:
        return keys

    mapping: Mapping[str, tuple[str, ...]]
    if scope == "global":
        mapping = GLOBAL_IMPLICATIONS
    else:
        mapping = WORKSPACE_IMPLICATIONS

    expanded = set(keys)
    queue = deque(keys)

    while queue:
        key = queue.popleft()
        for implied in mapping.get(key, ()):  # default empty tuple when no mapping
            if implied not in expanded:
                expanded.add(implied)
                queue.append(implied)

        if scope == "workspace" and key.startswith("Workspace."):
            if key.endswith(".ReadWrite"):
                read_variant = f"{key.removesuffix('.ReadWrite')}.Read"
                if read_variant in PERMISSION_REGISTRY and read_variant not in expanded:
                    expanded.add(read_variant)
                    queue.append(read_variant)

    if scope == "workspace" and expanded:
        workspace_read = "Workspace.Read"
        if workspace_read in PERMISSION_REGISTRY:
            expanded.add(workspace_read)

    return frozenset(expanded)


def _union_granted(granted: Iterable[str | Enum], *, scope: PermissionScope) -> frozenset[str]:
    keys = collect_permission_keys(granted)
    _validate_scope(keys, scope=scope)
    return _expand_implications(frozenset(keys), scope=scope)


def _slugify(value: str) -> str:
    candidate = _SLUG_PATTERN.sub("-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", candidate)


def _normalize_role_name(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise RoleValidationError("Role name is required")
    return candidate


def _normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    return candidate or None


def _normalize_permission_keys(
    permissions: Iterable[str], *, scope: PermissionScope
) -> tuple[str, ...]:
    collected = collect_permission_keys(permissions)
    _validate_scope(collected, scope=scope)
    return tuple(dict.fromkeys(collected))


async def _ensure_global_slug_available(
    *, session: AsyncSession, slug: str
) -> None:
    stmt = select(Role.id).where(
        Role.scope_type == "global",
        Role.scope_id.is_(None),
        Role.slug == slug,
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise RoleConflictError("Role slug already exists for the global scope")


def authorize_workspace(
    *, granted: Iterable[str | Enum], required: Iterable[str | Enum]
) -> AuthorizationDecision:
    """Authorize workspace-scoped permissions using the registry."""

    granted_keys = _union_granted(granted, scope="workspace")
    required_keys = collect_permission_keys(required)
    _validate_scope(required_keys, scope="workspace")
    missing = tuple(sorted(set(required_keys) - granted_keys))
    return AuthorizationDecision(
        granted=granted_keys,
        required=tuple(dict.fromkeys(required_keys)),
        missing=missing,
    )


def authorize_global(
    *, granted: Iterable[str | Enum], required: Iterable[str | Enum]
) -> AuthorizationDecision:
    """Authorize global permissions using the registry."""

    granted_keys = _union_granted(granted, scope="global")
    required_keys = collect_permission_keys(required)
    _validate_scope(required_keys, scope="global")
    missing = tuple(sorted(set(required_keys) - granted_keys))
    return AuthorizationDecision(
        granted=granted_keys,
        required=tuple(dict.fromkeys(required_keys)),
        missing=missing,
    )


async def _select_principal_for_user(
    *, session: AsyncSession, user_id: str
) -> Principal | None:
    result = await session.execute(
        select(Principal).where(Principal.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def ensure_user_principal(*, session: AsyncSession, user: User) -> Principal:
    """Return the ``Principal`` for ``user`` creating it when absent."""

    existing_principal = user.__dict__.get("principal")
    if existing_principal is not None:
        return existing_principal

    principal = await _select_principal_for_user(session=session, user_id=user.id)
    if principal is not None:
        return principal

    principal = Principal(principal_type="user", user_id=user.id)
    session.add(principal)
    await session.flush([principal])
    await session.refresh(principal)
    user.principal = principal
    return principal


async def get_global_permissions_for_principal(
    *, session: AsyncSession, principal: Principal
) -> frozenset[str]:
    """Return the flattened global permission set for ``principal``."""

    if principal.principal_type != "user":
        return frozenset()

    user = principal.user
    if user is None or user.is_service_account:
        return frozenset()

    stmt: Select[str] = (
        select(RolePermission.permission_key)
        .join(Role, Role.id == RolePermission.role_id)
        .join(RoleAssignment, RoleAssignment.role_id == Role.id)
        .where(
            RoleAssignment.principal_id == principal.id,
            RoleAssignment.scope_type == "global",
        )
    )
    result = await session.execute(stmt)
    permissions = frozenset(result.scalars().all())
    if not permissions:
        return permissions
    return _expand_implications(permissions, scope="global")


async def get_global_permissions_for_user(
    *, session: AsyncSession, user: User
) -> frozenset[str]:
    """Return the flattened global permission set for ``user``."""

    if user.is_service_account:
        return frozenset()

    principal = await _select_principal_for_user(session=session, user_id=user.id)
    if principal is None:
        return frozenset()

    return await get_global_permissions_for_principal(
        session=session, principal=principal
    )


async def get_workspace_permissions_for_principal(
    *, session: AsyncSession, principal: Principal, workspace_id: str
) -> frozenset[str]:
    """Return the flattened workspace permission set for ``principal``."""

    if principal.principal_type != "user":
        return frozenset()

    user = principal.user
    if user is None or user.is_service_account:
        return frozenset()

    stmt: Select[str] = (
        select(RolePermission.permission_key)
        .join(Role, Role.id == RolePermission.role_id)
        .join(RoleAssignment, RoleAssignment.role_id == Role.id)
        .where(
            RoleAssignment.principal_id == principal.id,
            RoleAssignment.scope_type == "workspace",
            RoleAssignment.scope_id == workspace_id,
        )
    )
    result = await session.execute(stmt)
    permissions = frozenset(result.scalars().all())
    if permissions:
        return _expand_implications(permissions, scope="workspace")

    global_permissions = await get_global_permissions_for_principal(
        session=session, principal=principal
    )
    if "Workspaces.ReadWrite.All" in global_permissions:
        for definition in SYSTEM_ROLES:
            if (
                definition.slug == "workspace-owner"
                and definition.scope_type == "workspace"
            ):
                return _expand_implications(
                    frozenset(definition.permissions), scope="workspace"
                )

    return permissions


async def get_workspace_permissions_for_user(
    *, session: AsyncSession, user: User, workspace_id: str
) -> frozenset[str]:
    """Return the flattened workspace permission set for ``user``."""

    if user.is_service_account:
        return frozenset()

    principal = await _select_principal_for_user(session=session, user_id=user.id)
    if principal is None:
        return frozenset()

    return await get_workspace_permissions_for_principal(
        session=session, principal=principal, workspace_id=workspace_id
    )


async def get_role(*, session: AsyncSession, role_id: str) -> Role | None:
    """Return a role with permissions eagerly loaded."""

    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_global_role_slugs_for_user(
    *, session: AsyncSession, user: User
) -> frozenset[str]:
    """Return the global role slugs assigned to ``user``."""

    if user.is_service_account:
        return frozenset()

    principal = await _select_principal_for_user(session=session, user_id=user.id)
    if principal is None:
        return frozenset()

    stmt: Select[str] = (
        select(Role.slug)
        .join(RoleAssignment, RoleAssignment.role_id == Role.id)
        .where(
            RoleAssignment.principal_id == principal.id,
            RoleAssignment.scope_type == "global",
        )
    )
    result = await session.execute(stmt)
    return frozenset(result.scalars().all())


async def get_global_role_by_slug(
    *, session: AsyncSession, slug: str
) -> Role | None:
    """Return the global role matching ``slug`` if present."""

    stmt = (
        select(Role)
        .where(Role.slug == slug, Role.scope_type == "global", Role.scope_id.is_(None))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def count_users_with_global_role(
    *, session: AsyncSession, slug: str
) -> int:
    """Return the number of users assigned the global role ``slug``."""

    stmt = (
        select(func.count())
        .select_from(RoleAssignment)
        .join(Role, Role.id == RoleAssignment.role_id)
        .join(Principal, Principal.id == RoleAssignment.principal_id)
        .where(
            RoleAssignment.scope_type == "global",
            Role.slug == slug,
            Principal.principal_type == "user",
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


async def has_users_with_global_role(
    *, session: AsyncSession, slug: str
) -> bool:
    """Return ``True`` when at least one user has the global role ``slug``."""

    stmt = (
        select(RoleAssignment.id)
        .join(Role, Role.id == RoleAssignment.role_id)
        .join(Principal, Principal.id == RoleAssignment.principal_id)
        .where(
            RoleAssignment.scope_type == "global",
            Role.slug == slug,
            Principal.principal_type == "user",
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def list_roles(
    *, session: AsyncSession, scope_type: str, scope_id: str | None = None
) -> list[Role]:
    """Return roles for the requested scope ordered by slug."""

    if scope_type not in {"global", "workspace"}:
        raise RoleValidationError("Unsupported scope_type")

    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.scope_type == scope_type)
    )

    if scope_type == "global":
        stmt = stmt.where(Role.scope_id.is_(None))
    else:
        if scope_id is None:
            raise RoleValidationError("workspace_id is required for workspace roles")
        stmt = stmt.where(or_(Role.scope_id.is_(None), Role.scope_id == scope_id))

    stmt = stmt.order_by(Role.slug)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_global_role(
    *, session: AsyncSession, payload: "RoleCreate", actor: User
) -> Role:
    """Create a new global role."""

    normalized_name = _normalize_role_name(payload.name)
    slug_source = payload.slug or normalized_name
    slug = _slugify(slug_source)
    if not slug:
        raise RoleValidationError("Role slug is required")

    await _ensure_global_slug_available(session=session, slug=slug)

    try:
        permission_keys = _normalize_permission_keys(
            payload.permissions, scope="global"
        )
    except AuthorizationError as exc:
        raise RoleValidationError(str(exc)) from exc

    role = Role(
        scope_type="global",
        scope_id=None,
        slug=slug,
        name=normalized_name,
        description=_normalize_description(payload.description),
        built_in=False,
        editable=True,
        created_by=cast(str | None, getattr(actor, "id", None)),
        updated_by=cast(str | None, getattr(actor, "id", None)),
    )
    session.add(role)
    await session.flush([role])

    if permission_keys:
        session.add_all(
            [
                RolePermission(role_id=cast(str, role.id), permission_key=key)
                for key in permission_keys
            ]
        )

    await session.flush()
    await session.refresh(role, attribute_names=["permissions"])
    return role


async def update_global_role(
    *, session: AsyncSession, role_id: str, payload: "RoleUpdate", actor: User
) -> Role:
    """Update an editable global role."""

    role = await session.get(Role, role_id)
    if role is None or role.scope_type != "global":
        raise RoleNotFoundError("Role not found")
    if role.built_in or not role.editable:
        raise RoleImmutableError("System roles cannot be edited")

    role.name = _normalize_role_name(payload.name)
    role.description = _normalize_description(payload.description)
    role.updated_by = cast(str | None, getattr(actor, "id", None))

    try:
        permission_keys = set(
            _normalize_permission_keys(payload.permissions, scope="global")
        )
    except AuthorizationError as exc:
        raise RoleValidationError(str(exc)) from exc

    current = {permission.permission_key for permission in role.permissions}

    additions = sorted(permission_keys - current)
    removals = sorted(current - permission_keys)

    if additions:
        session.add_all(
            [
                RolePermission(role_id=cast(str, role.id), permission_key=key)
                for key in additions
            ]
        )

    if removals:
        await session.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_key.in_(removals),
            )
        )

    await session.flush()
    await session.refresh(role, attribute_names=["permissions"])
    return role


async def delete_global_role(*, session: AsyncSession, role_id: str) -> None:
    """Remove an editable global role when no assignments exist."""

    role = await session.get(Role, role_id)
    if role is None or role.scope_type != "global":
        raise RoleNotFoundError("Role not found")
    if role.built_in or not role.editable:
        raise RoleImmutableError("System roles cannot be deleted")

    assignment_exists = await session.execute(
        select(RoleAssignment.id).where(
            RoleAssignment.role_id == role.id,
            RoleAssignment.scope_type == "global",
        )
    )
    if assignment_exists.first() is not None:
        raise RoleConflictError("Role is assigned to one or more principals")

    await session.delete(role)
    await session.flush()


async def list_role_assignments(
    *,
    session: AsyncSession,
    scope_type: str,
    scope_id: str | None,
    principal_id: str | None = None,
    role_id: str | None = None,
) -> list[RoleAssignment]:
    """Return assignments for the requested scope filtered by optional criteria."""

    if scope_type not in {"global", "workspace"}:
        raise RoleScopeMismatchError("Unsupported scope_type")

    conditions = [RoleAssignment.scope_type == scope_type]
    if scope_type == "global":
        if scope_id not in (None, ""):
            raise RoleScopeMismatchError("Global assignments must omit scope_id")
        conditions.append(RoleAssignment.scope_id.is_(None))
    else:
        if scope_id is None:
            raise RoleScopeMismatchError("Workspace assignments require scope_id")
        conditions.append(RoleAssignment.scope_id == scope_id)

    if principal_id:
        conditions.append(RoleAssignment.principal_id == principal_id)
    if role_id:
        conditions.append(RoleAssignment.role_id == role_id)

    stmt = (
        select(RoleAssignment)
        .options(
            selectinload(RoleAssignment.role),
            selectinload(RoleAssignment.principal).selectinload(Principal.user),
        )
        .where(*conditions)
        .order_by(RoleAssignment.created_at, RoleAssignment.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_role_assignment(
    *,
    session: AsyncSession,
    principal_id: str,
    role_id: str,
    scope_type: str,
    scope_id: str | None,
) -> RoleAssignment | None:
    """Return a single assignment for the provided identifiers."""

    assignments = await list_role_assignments(
        session=session,
        scope_type=scope_type,
        scope_id=scope_id,
        principal_id=principal_id,
        role_id=role_id,
    )
    if not assignments:
        return None
    return assignments[0]


async def get_role_assignment_by_id(
    *, session: AsyncSession, assignment_id: str
) -> RoleAssignment | None:
    """Return a role assignment by its identifier with relationships loaded."""

    stmt = (
        select(RoleAssignment)
        .options(
            selectinload(RoleAssignment.role),
            selectinload(RoleAssignment.principal).selectinload(Principal.user),
        )
        .where(RoleAssignment.id == assignment_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def assign_role(
    *,
    session: AsyncSession,
    principal_id: str,
    role_id: str,
    scope_type: str,
    scope_id: str | None,
) -> RoleAssignment:
    """Assign ``role_id`` to ``principal_id`` for the provided scope."""

    principal = await session.get(Principal, principal_id)
    if principal is None:
        msg = f"Principal '{principal_id}' not found"
        raise PrincipalNotFoundError(msg)

    role = await session.get(Role, role_id)
    if role is None:
        msg = f"Role '{role_id}' not found"
        raise RoleNotFoundError(msg)

    if role.scope_type != scope_type:
        msg = "Role scope_type mismatch"
        raise RoleScopeMismatchError(msg)

    if scope_type == "global" and scope_id is not None:
        msg = "Global assignments must not specify scope_id"
        raise RoleScopeMismatchError(msg)
    if scope_type == "workspace" and scope_id is None:
        msg = "Workspace assignments require a scope_id"
        raise RoleScopeMismatchError(msg)
    if scope_type == "workspace" and role.scope_id is not None and role.scope_id != scope_id:
        msg = "Role is bound to a different workspace"
        raise RoleScopeMismatchError(msg)

    if scope_type == "workspace" and scope_id is not None:
        workspace = await session.get(Workspace, scope_id)
        if workspace is None:
            msg = f"Workspace '{scope_id}' not found"
            raise WorkspaceNotFoundError(msg)

    existing_stmt = select(RoleAssignment).where(
        RoleAssignment.principal_id == principal_id,
        RoleAssignment.role_id == role_id,
        RoleAssignment.scope_type == scope_type,
        RoleAssignment.scope_id.is_(None)
        if scope_id is None
        else RoleAssignment.scope_id == scope_id,
    )
    existing_assignment = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing_assignment is not None:
        return existing_assignment

    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    values = {
        "principal_id": principal_id,
        "role_id": role_id,
        "scope_type": scope_type,
        "scope_id": scope_id,
    }

    if dialect == "postgresql":
        stmt = (
            pg_insert(RoleAssignment)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=[
                    RoleAssignment.principal_id,
                    RoleAssignment.role_id,
                    RoleAssignment.scope_type,
                    RoleAssignment.scope_id,
                ]
            )
            .returning(RoleAssignment.assignment_id)
        )
        result = await session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is not None:
            assignment = await session.get(RoleAssignment, inserted_id)
            if assignment is not None:
                return assignment
    elif dialect == "sqlite":
        stmt = sqlite_insert(RoleAssignment).values(**values)
        stmt = stmt.prefix_with("OR IGNORE")
        await session.execute(stmt)
    else:
        async with session.begin_nested():
            assignment = RoleAssignment(**values)
            session.add(assignment)
            try:
                await session.flush([assignment])
            except IntegrityError:
                # Another transaction created the same assignment concurrently.
                pass
            else:
                await session.refresh(assignment)
                return assignment

    refreshed_assignment = (
        await session.execute(existing_stmt)
    ).scalar_one_or_none()
    if refreshed_assignment is None:
        msg = "Role assignment insert failed to materialise"
        raise RuntimeError(msg)
    return refreshed_assignment


async def assign_global_role(
    *, session: AsyncSession, user_id: str, role_id: str
) -> RoleAssignment:
    """Assign a global role to the user ``user_id``."""

    user = await session.get(User, user_id)
    if user is None:
        msg = f"User '{user_id}' not found"
        raise ValueError(msg)

    principal = await ensure_user_principal(session=session, user=user)
    return await assign_role(
        session=session,
        principal_id=principal.id,
        role_id=role_id,
        scope_type="global",
        scope_id=None,
    )


async def delete_role_assignment(
    *,
    session: AsyncSession,
    assignment_id: str,
    scope_type: str,
    scope_id: str | None,
) -> None:
    """Delete a role assignment ensuring scope alignment."""

    assignment = await session.get(RoleAssignment, assignment_id)
    if assignment is None:
        raise RoleAssignmentNotFoundError("Role assignment not found")

    if assignment.scope_type != scope_type:
        raise RoleAssignmentNotFoundError("Role assignment not found")

    if scope_type == "global":
        if assignment.scope_id is not None:
            raise RoleAssignmentNotFoundError("Role assignment not found")
    elif scope_type == "workspace":
        if scope_id is None or assignment.scope_id != scope_id:
            raise RoleAssignmentNotFoundError("Role assignment not found")
    else:
        raise RoleScopeMismatchError("Unsupported scope_type")

    await session.delete(assignment)
    await session.flush()


async def unassign_role(
    *,
    session: AsyncSession,
    principal_id: str,
    role_id: str,
    scope_type: str,
    scope_id: str | None,
) -> None:
    """Remove a role assignment if present."""

    await session.execute(
        delete(RoleAssignment).where(
            RoleAssignment.principal_id == principal_id,
            RoleAssignment.role_id == role_id,
            RoleAssignment.scope_type == scope_type,
            RoleAssignment.scope_id.is_(scope_id)
            if scope_id is None
            else RoleAssignment.scope_id == scope_id,
        )
    )
    await session.flush()


async def sync_permission_registry(*, session: AsyncSession) -> None:
    """Synchronise the ``permissions`` and system ``roles`` tables."""

    registry = {definition.key: definition for definition in PERMISSIONS}
    result = await session.execute(select(Permission))
    existing_permissions = {permission.key: permission for permission in result.scalars()}

    # Upsert registered permissions
    for definition in PERMISSIONS:
        record = existing_permissions.get(definition.key)
        if record is None:
            session.add(
                Permission(
                    key=definition.key,
                    resource=definition.resource,
                    action=definition.action,
                    scope_type=definition.scope,
                    label=definition.label,
                    description=definition.description,
                )
            )
        else:
            record.resource = definition.resource
            record.action = definition.action
            record.scope_type = definition.scope
            record.label = definition.label
            record.description = definition.description

    # Remove permissions that are no longer defined
    obsolete = set(existing_permissions) - set(registry)
    if obsolete:
        await session.execute(
            delete(Permission).where(Permission.key.in_(sorted(obsolete)))
        )

    await session.flush()

    # Sync system roles and their permissions
    role_slugs = [definition.slug for definition in SYSTEM_ROLES]
    result = await session.execute(
        select(Role).where(
            Role.slug.in_(role_slugs),
            Role.scope_id.is_(None),
        )
    )
    existing_roles = {role.slug: role for role in result.scalars()}

    for definition in SYSTEM_ROLES:
        role = existing_roles.get(definition.slug)
        if role is None:
            role = Role(
                slug=definition.slug,
                name=definition.name,
                scope_type=definition.scope_type,
                scope_id=None,
                description=definition.description,
                built_in=definition.built_in,
                editable=definition.editable,
            )
            session.add(role)
            await session.flush([role])
        else:
            role.name = definition.name
            role.scope_type = definition.scope_type
            role.scope_id = None
            role.description = definition.description
            role.built_in = definition.built_in
            role.editable = definition.editable

        result = await session.execute(
            select(RolePermission.permission_key).where(
                RolePermission.role_id == role.id
            )
        )
        current_permissions = set(result.scalars().all())
        desired_permissions = set(definition.permissions)

        for permission_key in desired_permissions - current_permissions:
            session.add(
                RolePermission(role_id=role.id, permission_key=permission_key)
            )

        extras = current_permissions - desired_permissions
        if extras:
            await session.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_key.in_(sorted(extras)),
                )
            )

    await session.commit()


__all__ = [
    "AuthorizationDecision",
    "AuthorizationError",
    "assign_global_role",
    "assign_role",
    "authorize_global",
    "authorize_workspace",
    "delete_role_assignment",
    "collect_permission_keys",
    "create_global_role",
    "count_users_with_global_role",
    "has_users_with_global_role",
    "delete_global_role",
    "ensure_user_principal",
    "get_global_permissions_for_principal",
    "get_global_permissions_for_user",
    "get_global_role_by_slug",
    "get_global_role_slugs_for_user",
    "get_role_assignment",
    "get_role_assignment_by_id",
    "get_role",
    "get_workspace_permissions_for_principal",
    "get_workspace_permissions_for_user",
    "list_roles",
    "list_role_assignments",
    "PrincipalNotFoundError",
    "RoleAssignmentError",
    "RoleAssignmentNotFoundError",
    "RoleConflictError",
    "RoleError",
    "RoleImmutableError",
    "RoleNotFoundError",
    "RoleScopeMismatchError",
    "RoleValidationError",
    "sync_permission_registry",
    "unassign_role",
    "update_global_role",
    "WorkspaceNotFoundError",
]
