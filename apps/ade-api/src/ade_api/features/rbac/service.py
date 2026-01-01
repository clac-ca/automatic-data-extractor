from __future__ import annotations

import logging
import re
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.listing import paginate_query, paginate_sequence
from ade_api.common.sorting import sort_sequence
from ade_api.core.rbac.policy import GLOBAL_IMPLICATIONS, WORKSPACE_IMPLICATIONS
from ade_api.core.rbac.registry import (
    PERMISSION_REGISTRY,
    PERMISSIONS,
    SYSTEM_ROLE_BY_SLUG,
    SYSTEM_ROLES,
    PermissionDef,
    role_allows_scope,
)
from ade_api.core.rbac.types import ScopeType
from ade_api.models import Permission, Role, RolePermission, User, UserRoleAssignment, Workspace

from .filters import (
    apply_assignment_filters,
    apply_permission_filters,
    evaluate_role_filters,
    parse_role_filters,
)
from .sorting import (
    ASSIGNMENT_DEFAULT_SORT,
    ASSIGNMENT_ID_FIELD,
    ASSIGNMENT_SORT_FIELDS,
    PERMISSION_DEFAULT_SORT,
    PERMISSION_ID_FIELD,
    PERMISSION_SORT_FIELDS,
    ROLE_DEFAULT_SORT,
    ROLE_SORT_FIELDS,
    role_id_key,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions / DTOs
# ---------------------------------------------------------------------------


class AuthorizationError(ValueError):
    """Raised when permission inputs are invalid or unregistered."""


class RoleError(ValueError):
    """Base class for role management errors."""


class RoleValidationError(RoleError):
    """Raised when a role payload is invalid."""


class RoleNotFoundError(RoleError):
    """Raised when a role cannot be located."""


class RoleImmutableError(RoleError):
    """Raised when attempting to mutate a system or non-editable role."""


class RoleConflictError(RoleError):
    """Raised when a role operation would violate uniqueness constraints."""


class AssignmentError(ValueError):
    """Base class for assignment errors."""


class AssignmentNotFoundError(AssignmentError):
    """Raised when a role assignment cannot be located."""


class ScopeMismatchError(AssignmentError):
    """Raised when a role assignment scope is invalid."""


@dataclass(frozen=True)
class AuthorizationDecision:
    """Result of an authorization evaluation."""

    granted: frozenset[str]
    required: tuple[str, ...]
    missing: tuple[str, ...]


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _normalize_permission_key(key: str | Any) -> str:
    normalized = str(key).strip()
    if not normalized:
        raise AuthorizationError("Permission key cannot be blank")
    if normalized not in PERMISSION_REGISTRY:
        raise AuthorizationError(f"Permission '{normalized}' is not registered")
    return normalized


def collect_permission_keys(keys: Iterable[str]) -> tuple[str, ...]:
    """Return normalized permission keys enforcing registry membership."""

    normalized = tuple(_normalize_permission_key(key) for key in keys)
    # Deduplicate while preserving order
    return tuple(dict.fromkeys(normalized))


def _validate_scope(keys: Sequence[str], *, scope: ScopeType) -> None:
    for key in keys:
        definition = PERMISSION_REGISTRY.get(key)
        if definition is None:
            raise AuthorizationError(f"Permission '{key}' is not registered")
        if definition.scope_type != scope:
            raise AuthorizationError(f"Permission '{key}' is not {scope}-scoped")


def _expand_implications(keys: frozenset[str], *, scope: ScopeType) -> frozenset[str]:
    """Expand a permission set with implied permissions."""
    if not keys:
        return keys

    mapping = GLOBAL_IMPLICATIONS if scope == ScopeType.GLOBAL else WORKSPACE_IMPLICATIONS
    expanded = set(keys)
    queue = deque(keys)

    while queue:
        key = queue.popleft()
        for implied in mapping.get(key, ()):
            if implied not in expanded:
                expanded.add(implied)
                queue.append(implied)

        # Heuristic: any workspace ".manage" implies ".read"
        if (
            scope == ScopeType.WORKSPACE
            and key.startswith("workspace.")
            and key.endswith(".manage")
        ):
            read_variant = key.replace(".manage", ".read")
            if read_variant not in expanded:
                expanded.add(read_variant)
                queue.append(read_variant)

    if scope == ScopeType.WORKSPACE and expanded:
        expanded.add("workspace.read")

    return frozenset(expanded)


def _role_permissions(role: Role) -> tuple[str, ...]:
    return tuple(rp.permission.key for rp in role.permissions if rp.permission is not None)


_ALL_GLOBAL_PERMISSIONS = frozenset(
    key for key, definition in PERMISSION_REGISTRY.items() if definition.scope_type == ScopeType.GLOBAL
)
_ALL_WORKSPACE_PERMISSIONS = frozenset(
    key for key, definition in PERMISSION_REGISTRY.items() if definition.scope_type == ScopeType.WORKSPACE
)


def _all_permissions_for_scope(scope: ScopeType) -> frozenset[str]:
    if scope == ScopeType.GLOBAL:
        return _ALL_GLOBAL_PERMISSIONS
    return _ALL_WORKSPACE_PERMISSIONS


def _assignment_scope_filter(workspace_id: UUID | None):
    if workspace_id is None:
        return UserRoleAssignment.workspace_id.is_(None)
    return UserRoleAssignment.workspace_id == workspace_id


# ---------------------------------------------------------------------------
# RBAC service
# ---------------------------------------------------------------------------


class RbacService:
    """RBAC operations: registry sync, role CRUD, assignments, and evaluation."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        # Per-session cache to avoid re-querying for the same user repeatedly
        self._cache: dict[tuple[str, ...], Any] = session.info.setdefault("rbac_cache", {})

    # ------------- cache helpers -----------------

    def _get_cached(self, key: tuple[str, ...]) -> Any | None:
        return self._cache.get(key)

    def _set_cached(self, key: tuple[str, ...], value: Any) -> None:
        self._cache[key] = value

    # ------------- registry sync -----------------

    async def _permission_id_map(self, definitions: Iterable[PermissionDef]) -> dict[str, UUID]:
        keys = tuple(defn.key for defn in definitions)
        if not keys:
            return {}
        result = await self._session.execute(
            select(Permission.key, Permission.id).where(Permission.key.in_(keys))
        )
        return {key: permission_id for key, permission_id in result.all()}

    async def sync_permission_registry(self) -> None:
        """Upsert the canonical permission registry into the database."""

        logger.debug("rbac.permissions.sync.start")

        result = await self._session.execute(select(Permission))
        existing = {permission.key: permission for permission in result.scalars().all()}
        desired_keys = {definition.key for definition in PERMISSIONS}

        # Upsert all known permissions
        for definition in PERMISSIONS:
            current = existing.get(definition.key)
            if current is None:
                self._session.add(
                    Permission(
                        key=definition.key,
                        resource=definition.resource,
                        action=definition.action,
                        scope_type=definition.scope_type,
                        label=definition.label,
                        description=definition.description,
                    )
                )
                continue

            current.resource = definition.resource
            current.action = definition.action
            current.scope_type = definition.scope_type
            current.label = definition.label
            current.description = definition.description

        # Remove stale permissions
        stale_keys = set(existing) - desired_keys
        if stale_keys:
            await self._session.execute(
                delete(Permission).where(Permission.key.in_(tuple(stale_keys)))
            )

        await self._session.flush()

        logger.debug(
            "rbac.permissions.sync.success",
            extra={"total": len(PERMISSIONS), "removed": len(stale_keys)},
        )

    async def sync_system_roles(self) -> None:
        """Ensure system roles exist with the canonical permission set."""
        logger.debug("rbac.system_roles.sync.start")

        await self.sync_permission_registry()
        permission_map = await self._permission_id_map(PERMISSION_REGISTRY.values())

        for definition in SYSTEM_ROLES:
            role = await self._role_by_slug(definition.slug)
            if role is None:
                role = Role(
                    slug=definition.slug,
                    name=definition.name,
                    description=definition.description,
                    is_system=definition.is_system,
                    is_editable=definition.is_editable,
                )
                self._session.add(role)
                await self._session.flush([role])
            else:
                role.name = definition.name
                role.description = definition.description
                role.is_system = definition.is_system
                role.is_editable = definition.is_editable

            await self._session.flush([role])
            await self._sync_role_permissions(
                role=role,
                permission_keys=definition.permissions,
                permission_map=permission_map,
            )

        logger.debug("rbac.system_roles.sync.success")

    async def sync_registry(self) -> None:
        """Sync both permissions and system roles."""
        await self.sync_system_roles()

    # ------------- permission listing ------------

    async def list_permissions(
        self,
        *,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        order_by,
        page: int,
        per_page: int,
    ):
        stmt = select(Permission)
        stmt = apply_permission_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )
        return await paginate_query(
            self._session,
            stmt,
            page=page,
            per_page=per_page,
            order_by=order_by,
            changes_cursor="0",
        )

    # ------------- role CRUD ---------------------

    async def list_roles(
        self,
        *,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        sort: list[str],
        page: int,
        per_page: int,
    ):
        stmt: Select[Role] = (
            select(Role)
            .options(
                selectinload(Role.permissions).selectinload(RolePermission.permission),
            )
        )
        result = await self._session.execute(stmt)
        roles = list(result.scalars().all())
        parsed_filters = parse_role_filters(filters)
        filtered = [
            role
            for role in roles
            if evaluate_role_filters(
                role,
                parsed_filters,
                join_operator=join_operator,
                q=q,
            )
        ]
        ordered = sort_sequence(
            filtered,
            sort,
            allowed=ROLE_SORT_FIELDS,
            default=ROLE_DEFAULT_SORT,
            id_key=role_id_key,
        )
        return paginate_sequence(
            ordered,
            page=page,
            per_page=per_page,
            changes_cursor="0",
        )

    async def get_role(self, role_id: UUID) -> Role | None:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.id == role_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _role_by_slug(self, slug: str) -> Role | None:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.slug == slug)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_role_by_slug(self, *, slug: str) -> Role | None:
        return await self._role_by_slug(slug)

    async def create_role(
        self,
        *,
        name: str,
        slug: str | None,
        description: str | None,
        permissions: Sequence[str],
        actor: User | None,
    ) -> Role:
        normalized_name = _normalize_role_name(name)
        slug_value = _slugify(slug or normalized_name)
        if not slug_value:
            raise RoleValidationError("Role slug is required")

        if slug_value in SYSTEM_ROLE_BY_SLUG:
            raise RoleConflictError("Slug conflicts with a system role")

        existing = await self._role_by_slug(slug_value)
        if existing is not None:
            raise RoleConflictError("Role slug already exists")

        permission_keys = collect_permission_keys(permissions)

        role = Role(
            slug=slug_value,
            name=normalized_name,
            description=_normalize_description(description),
            is_system=False,
            is_editable=True,
            created_by_id=getattr(actor, "id", None),
            updated_by_id=getattr(actor, "id", None),
        )
        self._session.add(role)
        await self._session.flush([role])

        if permission_keys:
            permission_map = await self._permission_id_map(
                PERMISSION_REGISTRY[key] for key in permission_keys
            )
            await self._sync_role_permissions(
                role=role,
                permission_keys=permission_keys,
                permission_map=permission_map,
            )

        await self._session.refresh(role, attribute_names=["permissions"])
        return role

    async def update_role(
        self,
        *,
        role_id: UUID,
        name: str,
        description: str | None,
        permissions: Sequence[str],
        actor: User | None,
    ) -> Role:
        role = await self.get_role(role_id)
        if role is None:
            raise RoleNotFoundError("Role not found")
        if role.is_system or not role.is_editable:
            raise RoleImmutableError("System roles cannot be edited")

        role.name = _normalize_role_name(name)
        role.description = _normalize_description(description)
        role.updated_by_id = getattr(actor, "id", None)

        permission_keys = collect_permission_keys(permissions)
        permission_map = await self._permission_id_map(
            PERMISSION_REGISTRY[key] for key in permission_keys
        )
        await self._sync_role_permissions(
            role=role,
            permission_keys=permission_keys,
            permission_map=permission_map,
        )

        await self._session.refresh(role, attribute_names=["permissions"])
        return role

    async def delete_role(self, *, role_id: UUID) -> None:
        role = await self.get_role(role_id)
        if role is None:
            raise RoleNotFoundError("Role not found")
        if role.is_system or not role.is_editable:
            raise RoleImmutableError("System roles cannot be deleted")

        assignment_count = await self._count_assignments_for_role(role_id=role_id)
        if assignment_count:
            raise RoleConflictError("Role is assigned to one or more users")

        await self._session.delete(role)
        await self._session.flush()

    async def _sync_role_permissions(
        self,
        *,
        role: Role,
        permission_keys: Sequence[str],
        permission_map: dict[str, UUID],
    ) -> None:
        result = await self._session.execute(
            select(RolePermission)
            .options(selectinload(RolePermission.permission))
            .where(RolePermission.role_id == role.id)
        )
        current_permissions = result.scalars().all()
        current = {rp.permission.key: rp for rp in current_permissions if rp.permission}
        desired = set(permission_keys)

        additions = desired - set(current)
        removals = set(current) - desired

        if additions:
            missing = [key for key in additions if key not in permission_map]
            if missing:
                raise RoleValidationError(f"Permissions not found: {', '.join(sorted(missing))}")
            self._session.add_all([
                RolePermission(
                    role_id=role.id,
                    permission_id=permission_map[key],
                )
                for key in additions
            ])

        if removals:
            removal_ids = [current[key].permission_id for key in removals if key in current]
            if removal_ids:
                await self._session.execute(
                    delete(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id.in_(removal_ids),
                    )
                )

        await self._session.flush()

    # ------------- assignments -------------------

    async def list_assignments(
        self,
        *,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        order_by,
        page: int,
        per_page: int,
        default_active_only: bool = True,
    ):
        stmt: Select[UserRoleAssignment] = (
            select(UserRoleAssignment)
            .options(
                selectinload(UserRoleAssignment.user),
                selectinload(UserRoleAssignment.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission),
            )
        )
        stmt = apply_assignment_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
            default_active_only=default_active_only,
        )

        return await paginate_query(
            self._session,
            stmt,
            page=page,
            per_page=per_page,
            order_by=order_by,
            changes_cursor="0",
        )

    async def get_assignment(self, *, assignment_id: UUID) -> UserRoleAssignment | None:
        stmt = (
            select(UserRoleAssignment)
            .options(
                selectinload(UserRoleAssignment.user),
                selectinload(UserRoleAssignment.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission),
            )
            .where(UserRoleAssignment.id == assignment_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_assignment_for_user_role(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        workspace_id: UUID | None,
    ) -> UserRoleAssignment | None:
        stmt = (
            select(UserRoleAssignment)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.role_id == role_id,
                _assignment_scope_filter(workspace_id),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def assign_role(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        workspace_id: UUID | None,
    ) -> UserRoleAssignment:
        scope_type = ScopeType.WORKSPACE if workspace_id is not None else ScopeType.GLOBAL
        role = await self.get_role(role_id)
        if role is None:
            raise RoleNotFoundError("Role not found")
        if not role_allows_scope(role.slug, scope_type):
            raise ScopeMismatchError("Role cannot be assigned to this scope")

        user = await self._session.get(User, user_id)
        if user is None:
            raise AssignmentError("User not found")

        if workspace_id is not None:
            if await self._session.get(Workspace, workspace_id) is None:
                raise AssignmentError("Workspace not found")

        assignment = UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            workspace_id=workspace_id,
        )
        self._session.add(assignment)
        try:
            await self._session.flush([assignment])
        except IntegrityError as exc:
            logger.debug(
                "rbac.assign.conflict",
                extra={
                    "user_id": str(user_id),
                    "role_id": str(role_id),
                    "scope_type": scope_type.value,
                    "workspace_id": str(workspace_id) if workspace_id else None,
                },
            )
            raise RoleConflictError("Assignment already exists") from exc

        await self._session.refresh(
            assignment,
            attribute_names=["user", "role", "workspace"],
        )
        return assignment

    async def assign_role_if_missing(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        workspace_id: UUID | None,
    ) -> UserRoleAssignment:
        existing = await self.get_assignment_for_user_role(
            user_id=user_id,
            role_id=role_id,
            workspace_id=workspace_id,
        )
        if existing is not None:
            return existing
        try:
            return await self.assign_role(
                user_id=user_id,
                role_id=role_id,
                workspace_id=workspace_id,
            )
        except RoleConflictError:
            existing = await self.get_assignment_for_user_role(
                user_id=user_id,
                role_id=role_id,
                workspace_id=workspace_id,
            )
            if existing is None:  # very defensive
                raise
            return existing

    async def delete_assignment(
        self,
        *,
        assignment_id: UUID,
        workspace_id: UUID | None,
    ) -> None:
        assignment = await self.get_assignment(assignment_id=assignment_id)
        if assignment is None:
            raise AssignmentNotFoundError("Role assignment not found")

        if assignment.workspace_id != workspace_id:
            raise ScopeMismatchError("Scope mismatch for assignment deletion")

        await self._session.delete(assignment)
        await self._session.flush()

    async def _count_assignments_for_role(self, *, role_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(UserRoleAssignment)
            .where(UserRoleAssignment.role_id == role_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def has_assignments_for_role(
        self,
        *,
        role_id: UUID,
        workspace_id: UUID | None,
    ) -> bool:
        stmt = (
            select(UserRoleAssignment.id)
            .where(
                UserRoleAssignment.role_id == role_id,
                _assignment_scope_filter(workspace_id),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ------------- permission evaluation ---------

    async def get_global_permissions_for_user(self, *, user: User) -> frozenset[str]:
        if user.is_service_account:
            return frozenset()
        if user.is_superuser:
            return _expand_implications(_all_permissions_for_scope(ScopeType.GLOBAL), scope=ScopeType.GLOBAL)

        cache_key = ("global_permissions", str(user.id))
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        stmt: Select[str] = (
            select(Permission.key)
            .select_from(RolePermission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.workspace_id.is_(None),
                Permission.scope_type == ScopeType.GLOBAL,
            )
        )
        result = await self._session.execute(stmt)
        granted = frozenset(result.scalars().all())
        expanded = _expand_implications(granted, scope=ScopeType.GLOBAL)
        self._set_cached(cache_key, expanded)
        return expanded

    async def get_workspace_permissions_for_user(
        self,
        *,
        user: User,
        workspace_id: UUID,
    ) -> frozenset[str]:
        if user.is_service_account:
            return frozenset()
        if user.is_superuser:
            return _expand_implications(
                _all_permissions_for_scope(ScopeType.WORKSPACE),
                scope=ScopeType.WORKSPACE,
            )

        cache_key = ("workspace_permissions", str(user.id), str(workspace_id))
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        stmt: Select[str] = (
            select(Permission.key)
            .select_from(RolePermission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.workspace_id == workspace_id,
                Permission.scope_type == ScopeType.WORKSPACE,
            )
        )
        result = await self._session.execute(stmt)
        granted = frozenset(result.scalars().all())
        expanded = _expand_implications(granted, scope=ScopeType.WORKSPACE)

        # Global override: workspaces.manage_all grants all workspace permissions
        global_permissions = await self.get_global_permissions_for_user(user=user)
        if "workspaces.manage_all" in global_permissions:
            workspace_all = tuple(
                key
                for key, definition in PERMISSION_REGISTRY.items()
                if definition.scope_type == ScopeType.WORKSPACE
            )
            expanded = _expand_implications(
                expanded.union(workspace_all),
                scope=ScopeType.WORKSPACE,
            )

        self._set_cached(cache_key, expanded)
        return expanded

    async def authorize(
        self,
        *,
        user: User,
        permission_key: str,
        workspace_id: UUID | None = None,
    ) -> AuthorizationDecision:
        normalized = _normalize_permission_key(permission_key)
        definition = PERMISSION_REGISTRY[normalized]
        required = (normalized,)

        if user.is_superuser:
            granted = _all_permissions_for_scope(definition.scope_type)
            return AuthorizationDecision(granted=granted, required=required, missing=())

        if definition.scope_type == ScopeType.GLOBAL:
            granted = await self.get_global_permissions_for_user(user=user)
            missing = tuple(sorted(set(required) - granted))
            return AuthorizationDecision(granted=granted, required=required, missing=missing)

        # Workspace-scoped
        if workspace_id is None:
            raise AuthorizationError("workspace_id is required for workspace permissions")

        workspace_permissions = await self.get_workspace_permissions_for_user(
            user=user,
            workspace_id=workspace_id,
        )
        missing = tuple(sorted(set(required) - workspace_permissions))
        return AuthorizationDecision(
            granted=workspace_permissions,
            required=required,
            missing=missing,
        )

    async def get_global_role_slugs_for_user(self, *, user: User) -> frozenset[str]:
        if user.is_service_account:
            return frozenset()

        cache_key = ("global_role_slugs", str(user.id))
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        stmt: Select[str] = (
            select(Role.slug)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.workspace_id.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        slugs = frozenset(result.scalars().all())
        self._set_cached(cache_key, slugs)
        return slugs

    # Convenience wrappers for dependencies / routers ------------------

    async def has_permission_for_user_id(
        self,
        *,
        user_id: UUID,
        permission_key: str,
        workspace_id: UUID | None = None,
    ) -> bool:
        user = await self._session.get(User, user_id)
        if user is None:
            return False
        decision = await self.authorize(
            user=user,
            permission_key=permission_key,
            workspace_id=workspace_id,
        )
        return not decision.missing


# Convenience function if you ever need it outside of dependency wiring
async def authorize(
    *,
    session: AsyncSession,
    user: User,
    permission_key: str,
    workspace_id: UUID | None = None,
) -> AuthorizationDecision:
    service = RbacService(session=session)
    return await service.authorize(
        user=user,
        permission_key=permission_key,
        workspace_id=workspace_id,
    )
