"""Service functions for ADE's unified RBAC implementation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from collections import deque
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import cast

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ade_api.features.users.models import User
from ade_api.features.workspaces.models import Workspace
from ade_api.shared.core.logging import log_context
from ade_api.shared.pagination import Page, paginate_sql

from ..system_settings.models import SystemSetting
from .models import (
    Permission,
    Principal,
    PrincipalType,
    Role,
    RoleAssignment,
    RolePermission,
    ScopeType,
)
from .registry import (
    PERMISSION_REGISTRY,
    PERMISSIONS,
    SYSTEM_ROLES,
    PermissionScope,
)
from .schemas import RoleCreate, RoleUpdate

logger = logging.getLogger(__name__)

_REGISTRY_SYNCED = False
_REGISTRY_LOCK = asyncio.Lock()
_REGISTRY_VERSION_KEY = "roles-registry-version"
_REGISTRY_CACHE_TTL = timedelta(minutes=10)
_registry_cache_expires_at: datetime | None = None
_registry_cached_version: str | None = None
_GLOBAL_ROLE_CACHE_TTL = timedelta(minutes=10)
_global_role_cache_expires_at: datetime | None = None
_global_role_cache: dict[str, str] = {}

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
    if scope == ScopeType.GLOBAL:
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

        if scope == ScopeType.WORKSPACE and key.startswith("Workspace."):
            if key.endswith(".ReadWrite"):
                read_variant = f"{key.removesuffix('.ReadWrite')}.Read"
                if read_variant in PERMISSION_REGISTRY and read_variant not in expanded:
                    expanded.add(read_variant)
                    queue.append(read_variant)

    if scope == ScopeType.WORKSPACE and expanded:
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


def _roles_query(scope_type: ScopeType, scope_id: str | None):
    if scope_type not in {ScopeType.GLOBAL, ScopeType.WORKSPACE}:
        raise RoleValidationError("Unsupported scope_type")

    stmt = (
        select(Role)
        .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        .where(Role.scope_type == scope_type)
    )
    if scope_type == ScopeType.GLOBAL:
        stmt = stmt.where(Role.scope_id.is_(None))
    else:
        if scope_id is None:
            raise RoleValidationError("workspace_id is required for workspace roles")
        stmt = stmt.where(or_(Role.scope_id.is_(None), Role.scope_id == scope_id))
    return stmt


def _normalize_permission_keys(
    permissions: Iterable[str], *, scope: PermissionScope
) -> tuple[str, ...]:
    collected = collect_permission_keys(permissions)
    _validate_scope(collected, scope=scope)
    return tuple(dict.fromkeys(collected))


async def resolve_permission_ids(
    session: AsyncSession, keys: Collection[str]
) -> dict[str, str]:
    """Return a mapping of permission keys to their primary keys."""

    if not keys:
        return {}

    logger.debug(
        "roles.permissions.resolve.start",
        extra=log_context(permission_count=len(keys)),
    )

    stmt = select(Permission.key, Permission.id).where(Permission.key.in_(tuple(keys)))
    result = await session.execute(stmt)
    mapping = {key: permission_id for key, permission_id in result.all()}
    missing = set(keys) - set(mapping)
    if missing:
        missing_list = ", ".join(sorted(missing))
        logger.warning(
            "roles.permissions.resolve.missing",
            extra=log_context(missing_keys=missing_list),
        )
        raise RoleValidationError(f"Permissions not found: {missing_list}")

    logger.debug(
        "roles.permissions.resolve.success",
        extra=log_context(permission_count=len(mapping)),
    )
    return mapping


async def _ensure_global_slug_available(
    *, session: AsyncSession, slug: str
) -> None:
    stmt = select(Role.id).where(
        Role.scope_type == ScopeType.GLOBAL,
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

    granted_keys = _union_granted(granted, scope=ScopeType.WORKSPACE)
    required_keys = collect_permission_keys(required)
    _validate_scope(required_keys, scope=ScopeType.WORKSPACE)
    missing = tuple(sorted(set(required_keys) - granted_keys))

    decision = AuthorizationDecision(
        granted=granted_keys,
        required=tuple(dict.fromkeys(required_keys)),
        missing=missing,
    )

    if missing:
        logger.debug(
            "auth.workspace.denied",
            extra=log_context(
                required=list(decision.required),
                missing=list(decision.missing),
                granted_count=len(decision.granted),
            ),
        )
    return decision


def authorize_global(
    *, granted: Iterable[str | Enum], required: Iterable[str | Enum]
) -> AuthorizationDecision:
    """Authorize global permissions using the registry."""

    granted_keys = _union_granted(granted, scope=ScopeType.GLOBAL)
    required_keys = collect_permission_keys(required)
    _validate_scope(required_keys, scope=ScopeType.GLOBAL)
    missing = tuple(sorted(set(required_keys) - granted_keys))

    decision = AuthorizationDecision(
        granted=granted_keys,
        required=tuple(dict.fromkeys(required_keys)),
        missing=missing,
    )

    if missing:
        logger.debug(
            "auth.global.denied",
            extra=log_context(
                required=list(decision.required),
                missing=list(decision.missing),
                granted_count=len(decision.granted),
            ),
        )
    return decision


async def _select_principal_for_user(
    *, session: AsyncSession, user_id: str
) -> Principal | None:
    return await session.get(Principal, user_id)


async def ensure_user_principal(*, session: AsyncSession, user: User) -> Principal:
    """Return the ``Principal`` for ``user`` creating it when absent."""

    principal = user.__dict__.get("principal") or await _select_principal_for_user(
        session=session, user_id=user.id
    )
    if principal is None:
        msg = "Principal lookup failed for user"
        raise PrincipalNotFoundError(msg)
    logger.debug(
        "roles.principal.ensure.found",
        extra=log_context(user_id=user.id, principal_id=principal.id),
    )
    return principal


async def get_global_permissions_for_principal(
    *, session: AsyncSession, principal: Principal
) -> frozenset[str]:
    """Return the flattened global permission set for ``principal``."""

    if principal.principal_type != PrincipalType.USER:
        return frozenset()

    user = principal.user
    if user is None or user.is_service_account:
        return frozenset()

    logger.debug(
        "roles.permissions.global.for_principal.start",
        extra=log_context(principal_id=principal.id, user_id=user.id),
    )

    stmt: Select[str] = (
        select(Permission.key)
        .select_from(RolePermission)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(RoleAssignment, RoleAssignment.role_id == Role.id)
        .where(
            RoleAssignment.principal_id == principal.id,
            RoleAssignment.scope_type == ScopeType.GLOBAL,
        )
    )
    result = await session.execute(stmt)
    permissions = frozenset(result.scalars().all())
    if not permissions:
        logger.debug(
            "roles.permissions.global.for_principal.empty",
            extra=log_context(principal_id=principal.id, user_id=user.id),
        )
        return permissions

    expanded = _expand_implications(permissions, scope=ScopeType.GLOBAL)
    logger.debug(
        "roles.permissions.global.for_principal.success",
        extra=log_context(
            principal_id=principal.id,
            user_id=user.id,
            permission_count=len(expanded),
        ),
    )
    return expanded


async def get_global_permissions_for_user(
    *, session: AsyncSession, user: User
) -> frozenset[str]:
    """Return the flattened global permission set for ``user``."""

    if user.is_service_account:
        return frozenset()

    principal = await _select_principal_for_user(session=session, user_id=user.id)
    if principal is None:
        logger.debug(
            "roles.permissions.global.for_user.no_principal",
            extra=log_context(user_id=user.id),
        )
        return frozenset()

    return await get_global_permissions_for_principal(
        session=session, principal=principal
    )


async def get_workspace_permissions_for_principal(
    *, session: AsyncSession, principal: Principal, workspace_id: str
) -> frozenset[str]:
    """Return the flattened workspace permission set for ``principal``."""

    if principal.principal_type != PrincipalType.USER:
        return frozenset()

    user = principal.user
    if user is None or user.is_service_account:
        return frozenset()

    logger.debug(
        "roles.permissions.workspace.for_principal.start",
        extra=log_context(principal_id=principal.id, user_id=user.id, workspace_id=workspace_id),
    )

    stmt: Select[str] = (
        select(Permission.key)
        .select_from(RolePermission)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(RoleAssignment, RoleAssignment.role_id == Role.id)
        .where(
            RoleAssignment.principal_id == principal.id,
            RoleAssignment.scope_type == ScopeType.WORKSPACE,
            RoleAssignment.scope_id == workspace_id,
        )
    )
    result = await session.execute(stmt)
    permissions = frozenset(result.scalars().all())
    if permissions:
        expanded = _expand_implications(permissions, scope=ScopeType.WORKSPACE)
        logger.debug(
            "roles.permissions.workspace.for_principal.success",
            extra=log_context(
                principal_id=principal.id,
                user_id=user.id,
                workspace_id=workspace_id,
                permission_count=len(expanded),
            ),
        )
        return expanded

    global_permissions = await get_global_permissions_for_principal(
        session=session, principal=principal
    )
    if "Workspaces.ReadWrite.All" in global_permissions:
        for definition in SYSTEM_ROLES:
            if (
                definition.slug == "workspace-owner"
                and definition.scope_type == ScopeType.WORKSPACE
            ):
                expanded = _expand_implications(
                    frozenset(definition.permissions), scope=ScopeType.WORKSPACE
                )
                logger.debug(
                    "roles.permissions.workspace.for_principal.derived_from_global",
                    extra=log_context(
                        principal_id=principal.id,
                        user_id=user.id,
                        workspace_id=workspace_id,
                        permission_count=len(expanded),
                    ),
                )
                return expanded

    logger.debug(
        "roles.permissions.workspace.for_principal.empty",
        extra=log_context(principal_id=principal.id, user_id=user.id, workspace_id=workspace_id),
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
        logger.debug(
            "roles.permissions.workspace.for_user.no_principal",
            extra=log_context(user_id=user.id, workspace_id=workspace_id),
        )
        return frozenset()

    return await get_workspace_permissions_for_principal(
        session=session, principal=principal, workspace_id=workspace_id
    )


async def get_role(*, session: AsyncSession, role_id: str) -> Role | None:
    """Return a role with permissions eagerly loaded."""

    logger.debug(
        "roles.get.start",
        extra=log_context(role_id=role_id),
    )

    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    result = await session.execute(stmt)
    role = result.scalar_one_or_none()

    logger.debug(
        "roles.get.completed",
        extra=log_context(role_id=role_id, found=bool(role)),
    )
    return role


async def get_global_role_slugs_for_user(
    *, session: AsyncSession, user: User
) -> frozenset[str]:
    """Return the global role slugs assigned to ``user``."""

    if user.is_service_account:
        return frozenset()

    principal = await _select_principal_for_user(session=session, user_id=user.id)
    if principal is None:
        return frozenset()

    logger.debug(
        "roles.global_slugs.for_user.start",
        extra=log_context(user_id=user.id, principal_id=principal.id),
    )

    stmt: Select[str] = (
        select(Role.slug)
        .join(RoleAssignment, RoleAssignment.role_id == Role.id)
        .where(
            RoleAssignment.principal_id == principal.id,
            RoleAssignment.scope_type == ScopeType.GLOBAL,
        )
    )
    result = await session.execute(stmt)
    slugs = frozenset(result.scalars().all())

    logger.debug(
        "roles.global_slugs.for_user.completed",
        extra=log_context(
            user_id=user.id,
            principal_id=principal.id,
            role_count=len(slugs),
        ),
    )
    return slugs


async def get_global_role_by_slug(
    *, session: AsyncSession, slug: str
) -> Role | None:
    """Return the global role matching ``slug`` if present."""

    global _global_role_cache_expires_at, _global_role_cache
    now = datetime.now(tz=UTC)
    cached_id = _global_role_cache.get(slug)
    if (
        cached_id is not None
        and _global_role_cache_expires_at is not None
        and now < _global_role_cache_expires_at
    ):
        logger.debug(
            "roles.global.get_by_slug.cached",
            extra=log_context(slug=slug, role_id=cached_id),
        )
        cached_role = await session.get(Role, cached_id)
        if cached_role is not None:
            return cached_role
        _global_role_cache.pop(slug, None)

    logger.debug(
        "roles.global.get_by_slug.start",
        extra=log_context(slug=slug),
    )

    stmt = (
        select(Role)
        .where(Role.slug == slug, Role.scope_type == ScopeType.GLOBAL, Role.scope_id.is_(None))
        .limit(1)
    )
    result = await session.execute(stmt)
    role = result.scalar_one_or_none()

    if role is not None:
        _global_role_cache[slug] = cast(str, role.id)
        _global_role_cache_expires_at = now + _GLOBAL_ROLE_CACHE_TTL
    else:
        _global_role_cache.pop(slug, None)

    logger.debug(
        "roles.global.get_by_slug.completed",
        extra=log_context(slug=slug, found=bool(role)),
    )
    return role


async def count_users_with_global_role(
    *, session: AsyncSession, slug: str
) -> int:
    """Return the number of users assigned the global role ``slug``."""

    logger.debug(
        "roles.global.count_users.start",
        extra=log_context(slug=slug),
    )

    stmt = (
        select(func.count())
        .select_from(RoleAssignment)
        .join(Role, Role.id == RoleAssignment.role_id)
        .join(Principal, Principal.id == RoleAssignment.principal_id)
        .where(
            RoleAssignment.scope_type == ScopeType.GLOBAL,
            Role.slug == slug,
            Principal.principal_type == PrincipalType.USER,
        )
    )
    result = await session.execute(stmt)
    count = int(result.scalar_one() or 0)

    logger.debug(
        "roles.global.count_users.completed",
        extra=log_context(slug=slug, user_count=count),
    )
    return count


async def has_users_with_global_role(
    *, session: AsyncSession, slug: str
) -> bool:
    """Return ``True`` when at least one user has the global role ``slug``."""

    logger.debug(
        "roles.global.has_users.start",
        extra=log_context(slug=slug),
    )

    stmt = (
        select(RoleAssignment.id)
        .join(Role, Role.id == RoleAssignment.role_id)
        .join(Principal, Principal.id == RoleAssignment.principal_id)
        .where(
            RoleAssignment.scope_type == ScopeType.GLOBAL,
            Role.slug == slug,
            Principal.principal_type == PrincipalType.USER,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    exists = result.scalar_one_or_none() is not None

    logger.debug(
        "roles.global.has_users.completed",
        extra=log_context(slug=slug, has_users=exists),
    )
    return exists


async def list_roles(
    *, session: AsyncSession, scope_type: ScopeType, scope_id: str | None = None
) -> list[Role]:
    """Return roles for the requested scope ordered by slug."""

    logger.debug(
        "roles.list.start",
        extra=log_context(scope_type=scope_type.value, scope_id=scope_id),
    )

    stmt = _roles_query(scope_type, scope_id).order_by(Role.slug)
    result = await session.execute(stmt)
    roles = list(result.scalars().all())

    logger.debug(
        "roles.list.completed",
        extra=log_context(scope_type=scope_type.value, scope_id=scope_id, count=len(roles)),
    )
    return roles


async def paginate_roles(
    *,
    session: AsyncSession,
    scope_type: ScopeType,
    scope_id: str | None,
    page: int,
    page_size: int,
    include_total: bool,
) -> Page[Role]:
    logger.debug(
        "roles.paginate.start",
        extra=log_context(
            scope_type=scope_type.value,
            scope_id=scope_id,
            page=page,
            page_size=page_size,
            include_total=include_total,
        ),
    )
    stmt = _roles_query(scope_type, scope_id)
    result = await paginate_sql(
        session,
        stmt,
        page=page,
        page_size=page_size,
        include_total=include_total,
        order_by=(Role.slug,),
    )
    logger.debug(
        "roles.paginate.completed",
        extra=log_context(
            scope_type=scope_type.value,
            scope_id=scope_id,
            page=page,
            page_size=page_size,
            include_total=include_total,
            count=len(result.items),
        ),
    )
    return result


def _role_assignments_query(
    *,
    scope_type: ScopeType,
    scope_id: str | None,
    principal_id: str | None,
    role_id: str | None,
):
    if scope_type == ScopeType.GLOBAL:
        target_scope_id = None
    else:
        if scope_id is None:
            raise RoleScopeMismatchError("Workspace assignments require scope_id")
        target_scope_id = scope_id

    stmt = (
        select(RoleAssignment)
        .options(
            selectinload(RoleAssignment.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission),
            selectinload(RoleAssignment.principal).selectinload(Principal.user),
        )
        .where(
            RoleAssignment.scope_type == scope_type,
            RoleAssignment.scope_id.is_(None)
            if target_scope_id is None
            else RoleAssignment.scope_id == target_scope_id,
        )
    )
    if principal_id:
        stmt = stmt.where(RoleAssignment.principal_id == principal_id)
    if role_id:
        stmt = stmt.where(RoleAssignment.role_id == role_id)
    return stmt


async def create_global_role(
    *, session: AsyncSession, payload: RoleCreate, actor: User
) -> Role:
    """Create a new global role."""

    normalized_name = _normalize_role_name(payload.name)
    slug_source = payload.slug or normalized_name
    slug = _slugify(slug_source)
    if not slug:
        raise RoleValidationError("Role slug is required")

    logger.debug(
        "roles.global.create.start",
        extra=log_context(
            slug=slug,
            role_name=normalized_name,
            actor_id=getattr(actor, "id", None),
        ),
    )

    await _ensure_global_slug_available(session=session, slug=slug)

    try:
        permission_keys = _normalize_permission_keys(
            payload.permissions, scope=ScopeType.GLOBAL
        )
    except AuthorizationError as exc:
        logger.warning(
            "roles.global.create.permission_validation_failed",
            extra=log_context(slug=slug, role_name=normalized_name),
        )
        raise RoleValidationError(str(exc)) from exc

    role = Role(
        scope_type=ScopeType.GLOBAL,
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
        permission_map = await resolve_permission_ids(session, permission_keys)
        session.add_all(
            [
                RolePermission(
                    role_id=cast(str, role.id),
                    permission_id=permission_map[key],
                )
                for key in permission_keys
            ]
        )

    await session.flush()
    await session.refresh(role, attribute_names=["permissions"])

    logger.info(
        "roles.global.create.success",
        extra=log_context(
            role_id=role.id,
            slug=role.slug,
            role_name=role.name,
            permission_count=len(permission_keys),
        ),
    )
    return role


async def update_global_role(
    *, session: AsyncSession, role_id: str, payload: RoleUpdate, actor: User
) -> Role:
    """Update an editable global role."""

    role = await session.get(Role, role_id)
    if role is None or role.scope_type != ScopeType.GLOBAL:
        logger.warning(
            "roles.global.update.not_found",
            extra=log_context(role_id=role_id),
        )
        raise RoleNotFoundError("Role not found")
    if role.built_in or not role.editable:
        logger.warning(
            "roles.global.update.immutable",
            extra=log_context(role_id=role_id, slug=role.slug),
        )
        raise RoleImmutableError("System roles cannot be edited")

    logger.debug(
        "roles.global.update.start",
        extra=log_context(
            role_id=role_id,
            slug=role.slug,
            actor_id=getattr(actor, "id", None),
        ),
    )

    role.name = _normalize_role_name(payload.name)
    role.description = _normalize_description(payload.description)
    role.updated_by = cast(str | None, getattr(actor, "id", None))

    try:
        permission_keys = set(
            _normalize_permission_keys(payload.permissions, scope=ScopeType.GLOBAL)
        )
    except AuthorizationError as exc:
        logger.warning(
            "roles.global.update.permission_validation_failed",
            extra=log_context(role_id=role_id, slug=role.slug),
        )
        raise RoleValidationError(str(exc)) from exc

    current_map = {
        permission.permission.key: permission.permission_id
        for permission in role.permissions
        if permission.permission is not None
    }
    current_keys = set(current_map)

    additions = sorted(permission_keys - current_keys)
    removals = sorted(current_keys - permission_keys)

    if additions:
        permission_map = await resolve_permission_ids(session, additions)
        session.add_all(
            [
                RolePermission(
                    role_id=cast(str, role.id),
                    permission_id=permission_map[key],
                )
                for key in additions
            ]
        )

    if removals:
        removal_ids = [current_map[key] for key in removals if key in current_map]
        if removal_ids:
            await session.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id.in_(removal_ids),
                )
            )

    await session.flush()
    await session.refresh(role, attribute_names=["permissions"])

    logger.info(
        "roles.global.update.success",
        extra=log_context(
            role_id=role.id,
            slug=role.slug,
            role_name=role.name,
            added=len(additions),
            removed=len(removals),
        ),
    )
    return role


async def delete_global_role(*, session: AsyncSession, role_id: str) -> None:
    """Remove an editable global role when no assignments exist."""

    role = await session.get(Role, role_id)
    if role is None or role.scope_type != ScopeType.GLOBAL:
        logger.warning(
            "roles.global.delete.not_found",
            extra=log_context(role_id=role_id),
        )
        raise RoleNotFoundError("Role not found")
    if role.built_in or not role.editable:
        logger.warning(
            "roles.global.delete.immutable",
            extra=log_context(role_id=role_id, slug=role.slug),
        )
        raise RoleImmutableError("System roles cannot be deleted")

    logger.debug(
        "roles.global.delete.start",
        extra=log_context(role_id=role_id, slug=role.slug),
    )

    assignment_exists = await session.execute(
        select(RoleAssignment.id).where(
            RoleAssignment.role_id == role.id,
            RoleAssignment.scope_type == ScopeType.GLOBAL,
        )
    )
    if assignment_exists.first() is not None:
        logger.warning(
            "roles.global.delete.in_use",
            extra=log_context(role_id=role_id, slug=role.slug),
        )
        raise RoleConflictError("Role is assigned to one or more principals")

    await session.delete(role)
    await session.flush()

    logger.info(
        "roles.global.delete.success",
        extra=log_context(role_id=role_id, slug=role.slug),
    )


async def list_role_assignments(
    *,
    session: AsyncSession,
    scope_type: ScopeType,
    scope_id: str | None,
    principal_id: str | None = None,
    role_id: str | None = None,
) -> list[RoleAssignment]:
    """Return assignments for the requested scope filtered by optional criteria."""

    logger.debug(
        "roles.assignments.list.start",
        extra=log_context(
            scope_type=scope_type.value,
            scope_id=scope_id,
            principal_id=principal_id,
            role_id=role_id,
        ),
    )

    stmt = _role_assignments_query(
        scope_type=scope_type,
        scope_id=scope_id,
        principal_id=principal_id,
        role_id=role_id,
    ).order_by(RoleAssignment.created_at, RoleAssignment.id)
    result = await session.execute(stmt)
    assignments = list(result.scalars().all())

    logger.debug(
        "roles.assignments.list.completed",
        extra=log_context(
            scope_type=scope_type.value,
            scope_id=scope_id,
            principal_id=principal_id,
            role_id=role_id,
            count=len(assignments),
        ),
    )
    return assignments


async def paginate_role_assignments(
    *,
    session: AsyncSession,
    scope_type: ScopeType,
    scope_id: str | None,
    principal_id: str | None = None,
    role_id: str | None = None,
    page: int,
    page_size: int,
    include_total: bool,
) -> Page[RoleAssignment]:
    logger.debug(
        "roles.assignments.paginate.start",
        extra=log_context(
            scope_type=scope_type.value,
            scope_id=scope_id,
            principal_id=principal_id,
            role_id=role_id,
            page=page,
            page_size=page_size,
            include_total=include_total,
        ),
    )
    stmt = _role_assignments_query(
        scope_type=scope_type,
        scope_id=scope_id,
        principal_id=principal_id,
        role_id=role_id,
    )
    result = await paginate_sql(
        session,
        stmt,
        page=page,
        page_size=page_size,
        include_total=include_total,
        order_by=(RoleAssignment.created_at, RoleAssignment.id),
    )

    logger.debug(
        "roles.assignments.paginate.completed",
        extra=log_context(
            scope_type=scope_type.value,
            scope_id=scope_id,
            principal_id=principal_id,
            role_id=role_id,
            page=page,
            page_size=page_size,
            include_total=include_total,
            count=len(result.items),
        ),
    )
    return result


async def get_role_assignment(
    *,
    session: AsyncSession,
    principal_id: str,
    role_id: str,
    scope_type: ScopeType,
    scope_id: str | None,
) -> RoleAssignment | None:
    """Return a single assignment for the provided identifiers."""

    logger.debug(
        "roles.assignments.get.start",
        extra=log_context(
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type.value,
            scope_id=scope_id,
        ),
    )

    assignments = await list_role_assignments(
        session=session,
        scope_type=scope_type,
        scope_id=scope_id,
        principal_id=principal_id,
        role_id=role_id,
    )
    assignment = assignments[0] if assignments else None

    logger.debug(
        "roles.assignments.get.completed",
        extra=log_context(
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type.value,
            scope_id=scope_id,
            found=bool(assignment),
        ),
    )
    return assignment


async def get_role_assignment_by_id(
    *, session: AsyncSession, assignment_id: str
) -> RoleAssignment | None:
    """Return a role assignment by its identifier with relationships loaded."""

    logger.debug(
        "roles.assignments.get_by_id.start",
        extra=log_context(assignment_id=assignment_id),
    )

    stmt = (
        select(RoleAssignment)
        .options(
            selectinload(RoleAssignment.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission),
            selectinload(RoleAssignment.principal).selectinload(Principal.user),
        )
        .where(RoleAssignment.id == assignment_id)
    )
    result = await session.execute(stmt)
    assignment = result.scalar_one_or_none()

    logger.debug(
        "roles.assignments.get_by_id.completed",
        extra=log_context(assignment_id=assignment_id, found=bool(assignment)),
    )
    return assignment


async def assign_role(
    *,
    session: AsyncSession,
    principal_id: str,
    role_id: str,
    scope_type: ScopeType,
    scope_id: str | None,
) -> RoleAssignment:
    """Assign ``role_id`` to ``principal_id`` for the provided scope."""

    logger.debug(
        "roles.assignments.assign.start",
        extra=log_context(
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type.value,
            scope_id=scope_id,
        ),
    )

    principal = await session.get(Principal, principal_id)
    if principal is None:
        msg = f"Principal '{principal_id}' not found"
        logger.warning(
            "roles.assignments.assign.principal_not_found",
            extra=log_context(principal_id=principal_id),
        )
        raise PrincipalNotFoundError(msg)

    role = await session.get(Role, role_id)
    if role is None:
        msg = f"Role '{role_id}' not found"
        logger.warning(
            "roles.assignments.assign.role_not_found",
            extra=log_context(role_id=role_id),
        )
        raise RoleNotFoundError(msg)

    if role.scope_type != scope_type:
        msg = "Role scope_type mismatch"
        logger.warning(
            "roles.assignments.assign.scope_type_mismatch",
            extra=log_context(
                role_id=role_id,
                role_scope_type=role.scope_type.value,
                requested_scope_type=scope_type.value,
            ),
        )
        raise RoleScopeMismatchError(msg)

    if scope_type == ScopeType.GLOBAL and scope_id is not None:
        msg = "Global assignments must not specify scope_id"
        logger.warning(
            "roles.assignments.assign.global_with_scope_id",
            extra=log_context(
                principal_id=principal_id,
                role_id=role_id,
                scope_type=scope_type.value,
                scope_id=scope_id,
            ),
        )
        raise RoleScopeMismatchError(msg)
    if scope_type == ScopeType.WORKSPACE and scope_id is None:
        msg = "Workspace assignments require a scope_id"
        logger.warning(
            "roles.assignments.assign.workspace_missing_scope_id",
            extra=log_context(
                principal_id=principal_id,
                role_id=role_id,
                scope_type=scope_type.value,
            ),
        )
        raise RoleScopeMismatchError(msg)
    if (
        scope_type == ScopeType.WORKSPACE
        and role.scope_id is not None
        and role.scope_id != scope_id
    ):
        msg = "Role is bound to a different workspace"
        logger.warning(
            "roles.assignments.assign.workspace_mismatch",
            extra=log_context(
                principal_id=principal_id,
                role_id=role_id,
                scope_type=scope_type.value,
                scope_id=scope_id,
                role_scope_id=role.scope_id,
            ),
        )
        raise RoleScopeMismatchError(msg)

    if scope_type == ScopeType.WORKSPACE and scope_id is not None:
        workspace = await session.get(Workspace, scope_id)
        if workspace is None:
            msg = f"Workspace '{scope_id}' not found"
            logger.warning(
                "roles.assignments.assign.workspace_not_found",
                extra=log_context(scope_id=scope_id),
            )
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
        logger.debug(
            "roles.assignments.assign.already_exists",
            extra=log_context(
                assignment_id=existing_assignment.id,
                principal_id=principal_id,
                role_id=role_id,
                scope_type=scope_type.value,
                scope_id=scope_id,
            ),
        )
        return existing_assignment

    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    workspace_id = scope_id if scope_type == ScopeType.WORKSPACE else None
    values = {
        "principal_id": principal_id,
        "role_id": role_id,
        "workspace_id": workspace_id,
    }

    if dialect == "postgresql":
        stmt = (
            pg_insert(RoleAssignment)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=[
                    RoleAssignment.principal_id,
                    RoleAssignment.role_id,
                    RoleAssignment.workspace_id,
                ]
            )
            .returning(RoleAssignment.id)
        )
        result = await session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is not None:
            assignment = await session.get(RoleAssignment, inserted_id)
            if assignment is not None:
                logger.info(
                    "roles.assignments.assign.created",
                    extra=log_context(
                        assignment_id=assignment.id,
                        principal_id=principal_id,
                        role_id=role_id,
                        scope_type=scope_type.value,
                        scope_id=scope_id,
                    ),
                )
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
                logger.debug(
                    "roles.assignments.assign.integrity_conflict",
                    extra=log_context(
                        principal_id=principal_id,
                        role_id=role_id,
                        scope_type=scope_type.value,
                        scope_id=scope_id,
                    ),
                )
            else:
                await session.refresh(assignment)
                logger.info(
                    "roles.assignments.assign.created",
                    extra=log_context(
                        assignment_id=assignment.id,
                        principal_id=principal_id,
                        role_id=role_id,
                        scope_type=scope_type.value,
                        scope_id=scope_id,
                    ),
                )
                return assignment

    refreshed_assignment = (await session.execute(existing_stmt)).scalar_one_or_none()
    if refreshed_assignment is None:
        msg = "Role assignment insert failed to materialise"
        logger.error(
            "roles.assignments.assign.failed_to_materialise",
            extra=log_context(
                principal_id=principal_id,
                role_id=role_id,
                scope_type=scope_type.value,
                scope_id=scope_id,
            ),
        )
        raise RuntimeError(msg)
    logger.info(
        "roles.assignments.assign.created_existing",
        extra=log_context(
            assignment_id=refreshed_assignment.id,
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type.value,
            scope_id=scope_id,
        ),
    )
    return refreshed_assignment


async def assign_global_role(
    *, session: AsyncSession, user_id: str, role_id: str
) -> RoleAssignment:
    """Assign a global role to the user ``user_id``."""

    logger.debug(
        "roles.assignments.assign_global.start",
        extra=log_context(user_id=user_id, role_id=role_id),
    )

    user = await session.get(User, user_id)
    if user is None:
        msg = f"User '{user_id}' not found"
        logger.warning(
            "roles.assignments.assign_global.user_not_found",
            extra=log_context(user_id=user_id),
        )
        raise ValueError(msg)

    principal = await ensure_user_principal(session=session, user=user)
    assignment = await assign_role(
        session=session,
        principal_id=principal.id,
        role_id=role_id,
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
    )

    logger.info(
        "roles.assignments.assign_global.success",
        extra=log_context(
            assignment_id=assignment.id,
            user_id=user_id,
            principal_id=principal.id,
            role_id=role_id,
        ),
    )
    return assignment


async def assign_global_role_if_missing(
    *, session: AsyncSession, user_id: str, role_id: str
) -> RoleAssignment | None:
    """Assign a global role if not already present.

    Returns the assignment when created; returns None when it already existed.
    """

    logger.debug(
        "roles.assignments.assign_global_if_missing.start",
        extra=log_context(user_id=user_id, role_id=role_id),
    )

    user = await session.get(User, user_id)
    if user is None:
        msg = f"User '{user_id}' not found"
        logger.warning(
            "roles.assignments.assign_global_if_missing.user_not_found",
            extra=log_context(user_id=user_id),
        )
        raise ValueError(msg)

    principal = await ensure_user_principal(session=session, user=user)

    existing_stmt = (
        select(RoleAssignment)
        .where(
            RoleAssignment.principal_id == principal.id,
            RoleAssignment.role_id == role_id,
            RoleAssignment.scope_type == ScopeType.GLOBAL,
            RoleAssignment.scope_id.is_(None),
        )
        .limit(1)
    )
    result = await session.execute(existing_stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        logger.debug(
            "roles.assignments.assign_global_if_missing.already_exists",
            extra=log_context(
                assignment_id=existing.id,
                user_id=user_id,
                principal_id=principal.id,
                role_id=role_id,
            ),
        )
        return None

    assignment = await assign_role(
        session=session,
        principal_id=principal.id,
        role_id=role_id,
        scope_type=ScopeType.GLOBAL,
        scope_id=None,
    )

    logger.info(
        "roles.assignments.assign_global_if_missing.created",
        extra=log_context(
            assignment_id=assignment.id,
            user_id=user_id,
            principal_id=principal.id,
            role_id=role_id,
        ),
    )
    return assignment


async def delete_role_assignment(
    *,
    session: AsyncSession,
    assignment_id: str,
    scope_type: ScopeType,
    scope_id: str | None,
) -> None:
    """Delete a role assignment ensuring scope alignment."""

    logger.debug(
        "roles.assignments.delete.start",
        extra=log_context(
            assignment_id=assignment_id,
            scope_type=scope_type.value,
            scope_id=scope_id,
        ),
    )

    assignment = await session.get(RoleAssignment, assignment_id)
    if assignment is None:
        logger.warning(
            "roles.assignments.delete.not_found",
            extra=log_context(assignment_id=assignment_id),
        )
        raise RoleAssignmentNotFoundError("Role assignment not found")

    if assignment.scope_type != scope_type:
        logger.warning(
            "roles.assignments.delete.scope_type_mismatch",
            extra=log_context(
                assignment_id=assignment_id,
                assignment_scope_type=assignment.scope_type.value,
                requested_scope_type=scope_type.value,
            ),
        )
        raise RoleAssignmentNotFoundError("Role assignment not found")

    if scope_type == ScopeType.GLOBAL:
        if assignment.scope_id is not None:
            raise RoleAssignmentNotFoundError("Role assignment not found")
    elif scope_type == ScopeType.WORKSPACE:
        if scope_id is None or assignment.scope_id != scope_id:
            raise RoleAssignmentNotFoundError("Role assignment not found")
    else:
        raise RoleScopeMismatchError("Unsupported scope_type")

    await session.delete(assignment)
    await session.flush()

    logger.info(
        "roles.assignments.delete.success",
        extra=log_context(
            assignment_id=assignment_id,
            scope_type=scope_type.value,
            scope_id=scope_id,
        ),
    )


async def unassign_role(
    *,
    session: AsyncSession,
    principal_id: str,
    role_id: str,
    scope_type: ScopeType,
    scope_id: str | None,
) -> None:
    """Remove a role assignment if present."""

    logger.debug(
        "roles.assignments.unassign.start",
        extra=log_context(
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type.value,
            scope_id=scope_id,
        ),
    )

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

    logger.info(
        "roles.assignments.unassign.success",
        extra=log_context(
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type.value,
            scope_id=scope_id,
        ),
    )


async def sync_permission_registry(*, session: AsyncSession, force: bool = False) -> None:
    """Synchronise the ``permissions`` and system ``roles`` tables.

    By default runs once per process to avoid repeated work on every request.
    Pass ``force=True`` for startup/maintenance flows that must refresh.
    """

    global _REGISTRY_SYNCED, _registry_cache_expires_at, _registry_cached_version

    now = datetime.now(tz=UTC)
    current_version = _compute_registry_version()

    existing_permission_count = await session.scalar(select(func.count()).select_from(Permission))
    existing_role_count = await session.scalar(select(func.count()).select_from(Role))
    existing_role_slugs = set(
        (
            await session.execute(
                select(Role.slug)
            )
        ).scalars()
    )
    missing_system_roles = {
        definition.slug for definition in SYSTEM_ROLES
    } - existing_role_slugs

    if (
        not force
        and _REGISTRY_SYNCED
        and _registry_cached_version == current_version
        and _registry_cache_expires_at is not None
        and now < _registry_cache_expires_at
        and existing_permission_count
        and existing_role_count
        and not missing_system_roles
    ):
        logger.debug(
            "roles.registry.sync.skip_cached",
            extra=log_context(version=current_version),
        )
        return

    async with _REGISTRY_LOCK:
        if (
            not force
            and _REGISTRY_SYNCED
            and _registry_cached_version == current_version
            and _registry_cache_expires_at is not None
            and now < _registry_cache_expires_at
        ):
            current_permission_count = await session.scalar(
                select(func.count()).select_from(Permission)
            )
            current_role_count = await session.scalar(
                select(func.count()).select_from(Role)
            )
            if current_permission_count and current_role_count and not missing_system_roles:
                logger.debug(
                    "roles.registry.sync.skip_cached_locked",
                    extra=log_context(version=current_version),
                )
                return
            # Cached version is valid but the DB is empty; force reseed
            force = True

        stored_version = await _fetch_registry_version(session=session)

        # If no version is persisted, always seed to ensure registry exists.
        if stored_version is None:
            logger.debug("roles.registry.sync.missing_version_seed", extra=log_context())
            force = True

        if not force and stored_version == current_version:
            existing_permission_count = await session.scalar(
                select(func.count()).select_from(Permission)
            )
            existing_role_count = await session.scalar(
                select(func.count()).select_from(Role)
            )
            if existing_permission_count and existing_role_count and not missing_system_roles:
                _REGISTRY_SYNCED = True
                _registry_cached_version = current_version
                _registry_cache_expires_at = now + _REGISTRY_CACHE_TTL
                logger.debug(
                    "roles.registry.sync.skip_persisted",
                    extra=log_context(version=current_version),
                )
                return
            # Missing data; force reseed
            force = True

        logger.info("roles.registry.sync.start", extra=log_context())

        registry = {definition.key: definition for definition in PERMISSIONS}
        result = await session.execute(select(Permission))
        existing_permissions = {
            permission.key: permission for permission in result.scalars()
        }

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
                select(Permission.key, RolePermission.permission_id)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            )
            current_permissions = {
                key: permission_id for key, permission_id in result.all()
            }
            desired_permissions = set(definition.permissions)

            additions = desired_permissions - set(current_permissions)
            if additions:
                permission_map = await resolve_permission_ids(session, additions)
                session.add_all(
                    [
                        RolePermission(
                            role_id=role.id,
                            permission_id=permission_map[key],
                        )
                        for key in additions
                    ]
                )

            extras = set(current_permissions) - desired_permissions
            if extras:
                removal_ids = [current_permissions[key] for key in extras]
                if removal_ids:
                    await session.execute(
                        delete(RolePermission).where(
                            RolePermission.role_id == role.id,
                            RolePermission.permission_id.in_(removal_ids),
                        )
                    )

        await session.commit()

        _REGISTRY_SYNCED = True
        _registry_cached_version = current_version
        _registry_cache_expires_at = now + _REGISTRY_CACHE_TTL
        await _persist_registry_version(
            session=session, version=current_version, synced_at=now
        )

        logger.info(
            "roles.registry.sync.success",
            extra=log_context(
                permission_count=len(PERMISSIONS),
                system_role_count=len(SYSTEM_ROLES),
            ),
        )


def _compute_registry_version() -> str:
    payload = {
        "permissions": [
            (
                definition.key,
                definition.resource,
                definition.action,
                definition.scope.value,
                definition.label,
                definition.description,
            )
            for definition in PERMISSIONS
        ],
        "system_roles": [
            (
                definition.slug,
                definition.name,
                definition.scope_type.value,
                definition.description,
                definition.permissions,
                definition.built_in,
                definition.editable,
            )
            for definition in SYSTEM_ROLES
        ],
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


async def _fetch_registry_version(*, session: AsyncSession) -> str | None:
    stmt = (
        select(SystemSetting)
        .where(SystemSetting.key == _REGISTRY_VERSION_KEY)
        .limit(1)
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    value = record.value if record else None
    if not value:
        return None
    version = value.get("version")
    return str(version) if version is not None else None


async def _persist_registry_version(
    *,
    session: AsyncSession,
    version: str,
    synced_at: datetime,
) -> None:
    payload = {"version": version, "synced_at": synced_at.isoformat()}
    result = await session.execute(
        select(SystemSetting)
        .where(SystemSetting.key == _REGISTRY_VERSION_KEY)
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record is None:
        record = SystemSetting(key=_REGISTRY_VERSION_KEY, value=payload)
        session.add(record)
    else:
        record.value = payload
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
    "resolve_permission_ids",
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
    "paginate_roles",
    "paginate_role_assignments",
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
