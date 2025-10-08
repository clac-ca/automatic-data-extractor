"""Authorization helpers and role utilities."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User, UserRole

from .models import Permission, Role, RolePermission, UserGlobalRole
from .registry import PERMISSIONS, PERMISSION_REGISTRY, PermissionScope, SYSTEM_ROLES


GLOBAL_IMPLICATIONS: Mapping[str, tuple[str, ...]] = {
    "Roles.ReadWrite.All": ("Roles.Read.All",),
    "System.Settings.ReadWrite": ("System.Settings.Read",),
    "Workspaces.ReadWrite.All": ("Workspaces.Read.All",),
}


WORKSPACE_IMPLICATIONS: Mapping[str, tuple[str, ...]] = {}


class AuthorizationError(ValueError):
    """Raised when permission inputs are invalid or unregistered."""


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


def authorize_workspace(*, granted: Iterable[str | Enum], required: Iterable[str | Enum]) -> AuthorizationDecision:
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


def authorize_global(*, granted: Iterable[str | Enum], required: Iterable[str | Enum]) -> AuthorizationDecision:
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


async def get_global_permissions_for_user(
    *, session: AsyncSession, user: User
) -> frozenset[str]:
    """Return the flattened global permission set for ``user``."""

    if user.role is UserRole.ADMIN:
        return frozenset(
            definition.key
            for definition in PERMISSION_REGISTRY.values()
            if definition.scope == "global"
        )

    stmt: Select[str] = (
        select(RolePermission.permission_key)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserGlobalRole, UserGlobalRole.role_id == Role.id)
        .where(
            UserGlobalRole.user_id == user.id,
            Role.scope == "global",
        )
    )
    result = await session.execute(stmt)
    return frozenset(result.scalars().all())


async def assign_global_role(
    *, session: AsyncSession, user_id: str, role_id: str
) -> None:
    """Assign ``role_id`` to ``user_id`` ensuring the role is global-scoped."""

    role = await session.get(Role, role_id)
    if role is None:
        msg = f"Role '{role_id}' not found"
        raise ValueError(msg)
    if role.scope != "global":
        msg = "Role assignments must use global-scoped roles"
        raise ValueError(msg)

    await session.merge(UserGlobalRole(user_id=user_id, role_id=role_id))
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
                    scope=definition.scope,
                    label=definition.label,
                    description=definition.description,
                )
            )
        else:
            record.scope = definition.scope
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
    system_scopes = {definition.scope for definition in SYSTEM_ROLES}
    result = await session.execute(
        select(Role).where(
            Role.slug.in_(role_slugs),
            Role.workspace_id.is_(None),
            Role.scope.in_(tuple(system_scopes)),
        )
    )
    existing_roles = {role.slug: role for role in result.scalars()}

    for definition in SYSTEM_ROLES:
        role = existing_roles.get(definition.slug)
        if role is None:
            role = Role(
                slug=definition.slug,
                name=definition.name,
                scope=definition.scope,
                workspace_id=None,
                description=definition.description,
                is_system=definition.is_system,
                editable=definition.editable,
            )
            session.add(role)
            await session.flush([role])
        else:
            role.name = definition.name
            role.scope = definition.scope
            role.workspace_id = None
            role.description = definition.description
            role.is_system = definition.is_system
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
    "authorize_global",
    "authorize_workspace",
    "collect_permission_keys",
    "assign_global_role",
    "get_global_permissions_for_user",
    "sync_permission_registry",
]
