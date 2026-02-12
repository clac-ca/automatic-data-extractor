from __future__ import annotations

import logging
import re
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, case, delete, func, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ade_api.common.cursor_listing import (
    CursorPage,
    ResolvedCursorSort,
    paginate_query_cursor,
)
from ade_api.common.list_filters import FilterItem, FilterJoinOperator
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
from ade_api.features.admin_settings.service import RuntimeSettingsService
from ade_db.models import (
    AssignmentScopeType,
    Group,
    GroupMembership,
    GroupSource,
    Permission,
    PrincipalType,
    Role,
    RoleAssignment,
    RolePermission,
    User,
    UserRoleAssignment,
    Workspace,
)

from .filters import (
    apply_assignment_filters,
    apply_permission_filters,
    apply_principal_assignment_filters,
    apply_role_filters,
)
from .sorting import PrincipalAssignmentRow

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
    key
    for key, definition in PERMISSION_REGISTRY.items()
    if definition.scope_type == ScopeType.GLOBAL
)
_ALL_WORKSPACE_PERMISSIONS = frozenset(
    key
    for key, definition in PERMISSION_REGISTRY.items()
    if definition.scope_type == ScopeType.WORKSPACE
)


def _all_permissions_for_scope(scope: ScopeType) -> frozenset[str]:
    if scope == ScopeType.GLOBAL:
        return _ALL_GLOBAL_PERMISSIONS
    return _ALL_WORKSPACE_PERMISSIONS


def _assignment_scope_filter(workspace_id: UUID | None) -> Any:
    if workspace_id is None:
        return UserRoleAssignment.workspace_id.is_(None)
    return UserRoleAssignment.workspace_id == workspace_id


def _assignment_scope_filter_v2(
    *,
    scope_type: AssignmentScopeType,
    scope_id: UUID | None,
) -> Any:
    if scope_type == AssignmentScopeType.ORGANIZATION:
        return and_(
            RoleAssignment.scope_type == AssignmentScopeType.ORGANIZATION,
            RoleAssignment.scope_id.is_(None),
        )
    return and_(
        RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
        RoleAssignment.scope_id == scope_id,
    )


def _map_principal_assignment_row(row: Mapping[str, Any]) -> PrincipalAssignmentRow:
    principal_type = row.get("principal_type")
    scope_type = row.get("scope_type")

    return PrincipalAssignmentRow(
        id=row["id"],
        principal_type=(
            principal_type
            if isinstance(principal_type, PrincipalType)
            else PrincipalType(str(principal_type))
        ),
        principal_id=row["principal_id"],
        role_id=row["role_id"],
        role_slug=str(row.get("role_slug") or ""),
        scope_type=(
            scope_type
            if isinstance(scope_type, AssignmentScopeType)
            else AssignmentScopeType(str(scope_type))
        ),
        scope_id=row.get("scope_id"),
        created_at=row["created_at"],
        principal_display_name=row.get("principal_display_name"),
        principal_email=row.get("principal_email"),
        principal_slug=row.get("principal_slug"),
    )


# ---------------------------------------------------------------------------
# RBAC service
# ---------------------------------------------------------------------------


class RbacService:
    """RBAC operations: registry sync, role CRUD, assignments, and evaluation."""

    def __init__(self, *, session: Session) -> None:
        self._session = session
        # Per-session cache to avoid re-querying for the same user repeatedly
        self._cache: dict[tuple[str, ...], Any] = session.info.setdefault("rbac_cache", {})

    # ------------- cache helpers -----------------

    def _get_cached(self, key: tuple[str, ...]) -> Any | None:
        return self._cache.get(key)

    def _set_cached(self, key: tuple[str, ...], value: Any) -> None:
        self._cache[key] = value

    def _effective_idp_provisioning_mode(self) -> str:
        cache_key = ("idp_provisioning_mode",)
        cached = self._get_cached(cache_key)
        if isinstance(cached, str):
            return cached

        try:
            mode = (
                RuntimeSettingsService(session=self._session)
                .get_effective_values()
                .auth.identity_provider.provisioning_mode
            )
        except Exception:
            logger.exception("rbac.provisioning_mode.resolve_failed")
            mode = "jit"

        self._set_cached(cache_key, mode)
        return mode

    def _idp_groups_allowed(self) -> bool:
        return self._effective_idp_provisioning_mode() == "scim"

    def _group_source_filter(self) -> Any:
        if self._idp_groups_allowed():
            return true()
        return Group.source == GroupSource.INTERNAL

    # ------------- registry sync -----------------

    def _permission_id_map(self, definitions: Iterable[PermissionDef]) -> dict[str, UUID]:
        keys = tuple(defn.key for defn in definitions)
        if not keys:
            return {}
        result = self._session.execute(
            select(Permission.key, Permission.id).where(Permission.key.in_(keys))
        )
        return {key: permission_id for key, permission_id in result.all()}

    def sync_permission_registry(self) -> None:
        """Upsert the canonical permission registry into the database."""

        logger.debug("rbac.permissions.sync.start")

        result = self._session.execute(select(Permission))
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
            self._session.execute(delete(Permission).where(Permission.key.in_(tuple(stale_keys))))

        self._session.flush()

        logger.debug(
            "rbac.permissions.sync.success",
            extra={"total": len(PERMISSIONS), "removed": len(stale_keys)},
        )

    def sync_system_roles(self) -> None:
        """Ensure system roles exist with the canonical permission set."""
        logger.debug("rbac.system_roles.sync.start")

        self.sync_permission_registry()
        permission_map = self._permission_id_map(PERMISSION_REGISTRY.values())

        for definition in SYSTEM_ROLES:
            role = self._role_by_slug(definition.slug)
            if role is None:
                role = Role(
                    slug=definition.slug,
                    name=definition.name,
                    description=definition.description,
                    is_system=definition.is_system,
                    is_editable=definition.is_editable,
                )
                self._session.add(role)
                self._session.flush([role])
            else:
                role.name = definition.name
                role.description = definition.description
                role.is_system = definition.is_system
                role.is_editable = definition.is_editable

            self._session.flush([role])
            self._sync_role_permissions(
                role=role,
                permission_keys=definition.permissions,
                permission_map=permission_map,
            )

        logger.debug("rbac.system_roles.sync.success")

    def sync_registry(self) -> None:
        """Sync both permissions and system roles."""
        self.sync_system_roles()

    # ------------- permission listing ------------

    def list_permissions(
        self,
        *,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        resolved_sort: ResolvedCursorSort[Permission],
        limit: int,
        cursor: str | None,
        include_total: bool,
    ) -> CursorPage[Permission]:
        stmt = select(Permission)
        stmt = apply_permission_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )
        return paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )

    # ------------- role CRUD ---------------------

    def list_roles(
        self,
        *,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        resolved_sort: ResolvedCursorSort[Role],
        limit: int,
        cursor: str | None,
        include_total: bool,
    ) -> CursorPage[Role]:
        stmt = select(Role).options(
            selectinload(Role.permissions).selectinload(RolePermission.permission),
        )
        stmt = apply_role_filters(
            stmt=stmt,
            filters=filters,
            join_operator=join_operator,
            q=q,
        )
        return paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )

    def get_role(self, role_id: UUID) -> Role | None:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.id == role_id)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _role_by_slug(self, slug: str) -> Role | None:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.slug == slug)
            .limit(1)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_role_by_slug(self, *, slug: str) -> Role | None:
        return self._role_by_slug(slug)

    def create_role(
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

        existing = self._role_by_slug(slug_value)
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
        self._session.flush([role])

        if permission_keys:
            permission_map = self._permission_id_map(
                PERMISSION_REGISTRY[key] for key in permission_keys
            )
            self._sync_role_permissions(
                role=role,
                permission_keys=permission_keys,
                permission_map=permission_map,
            )

        self._session.refresh(role, attribute_names=["permissions"])
        return role

    def update_role(
        self,
        *,
        role_id: UUID,
        name: str,
        description: str | None,
        permissions: Sequence[str],
        actor: User | None,
    ) -> Role:
        role = self.get_role(role_id)
        if role is None:
            raise RoleNotFoundError("Role not found")
        if role.is_system or not role.is_editable:
            raise RoleImmutableError("System roles cannot be edited")

        role.name = _normalize_role_name(name)
        role.description = _normalize_description(description)
        role.updated_by_id = getattr(actor, "id", None)

        permission_keys = collect_permission_keys(permissions)
        permission_map = self._permission_id_map(
            PERMISSION_REGISTRY[key] for key in permission_keys
        )
        self._sync_role_permissions(
            role=role,
            permission_keys=permission_keys,
            permission_map=permission_map,
        )

        self._session.refresh(role, attribute_names=["permissions"])
        return role

    def delete_role(self, *, role_id: UUID) -> None:
        role = self.get_role(role_id)
        if role is None:
            raise RoleNotFoundError("Role not found")
        if role.is_system or not role.is_editable:
            raise RoleImmutableError("System roles cannot be deleted")

        assignment_count = self._count_assignments_for_role(role_id=role_id)
        if assignment_count:
            raise RoleConflictError("Role is assigned to one or more users")

        self._session.delete(role)
        self._session.flush()

    def _sync_role_permissions(
        self,
        *,
        role: Role,
        permission_keys: Sequence[str],
        permission_map: dict[str, UUID],
    ) -> None:
        result = self._session.execute(
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
                self._session.execute(
                    delete(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id.in_(removal_ids),
                    )
                )

        self._session.flush()

    # ------------- assignments -------------------

    def list_assignments(
        self,
        *,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        resolved_sort: ResolvedCursorSort[UserRoleAssignment],
        limit: int,
        cursor: str | None,
        include_total: bool,
        default_active_only: bool = True,
    ) -> CursorPage[UserRoleAssignment]:
        stmt = select(UserRoleAssignment).options(
            selectinload(UserRoleAssignment.user),
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission),
        )
        stmt = apply_assignment_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
            default_active_only=default_active_only,
        )

        return paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
        )

    def get_assignment(self, *, assignment_id: UUID) -> UserRoleAssignment | None:
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
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_assignment_for_user_role(
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
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def assign_role(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        workspace_id: UUID | None,
    ) -> UserRoleAssignment:
        scope_type = ScopeType.WORKSPACE if workspace_id is not None else ScopeType.GLOBAL
        role = self.get_role(role_id)
        if role is None:
            raise RoleNotFoundError("Role not found")
        if not role_allows_scope(role.slug, scope_type):
            raise ScopeMismatchError("Role cannot be assigned to this scope")

        user = self._session.get(User, user_id)
        if user is None:
            raise AssignmentError("User not found")

        if workspace_id is not None:
            if self._session.get(Workspace, workspace_id) is None:
                raise AssignmentError("Workspace not found")

        assignment = UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            workspace_id=workspace_id,
        )
        self._session.add(assignment)
        try:
            self._session.flush([assignment])
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

        self._session.refresh(
            assignment,
            attribute_names=["user", "role", "workspace"],
        )
        mirror_scope_type = (
            AssignmentScopeType.WORKSPACE
            if workspace_id is not None
            else AssignmentScopeType.ORGANIZATION
        )
        self.assign_principal_role_if_missing(
            principal_type=PrincipalType.USER,
            principal_id=user.id,
            role_id=role.id,
            scope_type=mirror_scope_type,
            scope_id=workspace_id,
        )
        return assignment

    def assign_role_if_missing(
        self,
        *,
        user_id: UUID,
        role_id: UUID,
        workspace_id: UUID | None,
    ) -> UserRoleAssignment:
        existing = self.get_assignment_for_user_role(
            user_id=user_id,
            role_id=role_id,
            workspace_id=workspace_id,
        )
        if existing is not None:
            return existing
        try:
            return self.assign_role(
                user_id=user_id,
                role_id=role_id,
                workspace_id=workspace_id,
            )
        except RoleConflictError:
            existing = self.get_assignment_for_user_role(
                user_id=user_id,
                role_id=role_id,
                workspace_id=workspace_id,
            )
            if existing is None:  # very defensive
                raise
            return existing

    def delete_assignment(
        self,
        *,
        assignment_id: UUID,
        workspace_id: UUID | None,
    ) -> None:
        assignment = self.get_assignment(assignment_id=assignment_id)
        if assignment is None:
            raise AssignmentNotFoundError("Role assignment not found")

        if assignment.workspace_id != workspace_id:
            raise ScopeMismatchError("Scope mismatch for assignment deletion")

        mirror_scope_type = (
            AssignmentScopeType.WORKSPACE
            if assignment.workspace_id is not None
            else AssignmentScopeType.ORGANIZATION
        )
        mirror = self.get_principal_assignment_for_scope(
            principal_type=PrincipalType.USER,
            principal_id=assignment.user_id,
            role_id=assignment.role_id,
            scope_type=mirror_scope_type,
            scope_id=assignment.workspace_id,
        )
        if mirror is not None:
            self._session.delete(mirror)
        self._session.delete(assignment)
        self._session.flush()

    def list_principal_assignments(
        self,
        *,
        scope_type: AssignmentScopeType,
        scope_id: UUID | None,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
        resolved_sort: ResolvedCursorSort[PrincipalAssignmentRow],
        limit: int,
        cursor: str | None,
        include_total: bool,
    ) -> CursorPage[PrincipalAssignmentRow]:
        principal_display_name = case(
            (
                RoleAssignment.principal_type == PrincipalType.USER,
                func.coalesce(User.display_name, User.email),
            ),
            (
                RoleAssignment.principal_type == PrincipalType.GROUP,
                Group.display_name,
            ),
            else_=None,
        ).label("principal_display_name")
        principal_email = case(
            (RoleAssignment.principal_type == PrincipalType.USER, User.email),
            else_=None,
        ).label("principal_email")
        principal_slug = case(
            (RoleAssignment.principal_type == PrincipalType.GROUP, Group.slug),
            else_=None,
        ).label("principal_slug")

        stmt = (
            select(
                RoleAssignment.id.label("id"),
                RoleAssignment.principal_type.label("principal_type"),
                RoleAssignment.principal_id.label("principal_id"),
                RoleAssignment.role_id.label("role_id"),
                Role.slug.label("role_slug"),
                RoleAssignment.scope_type.label("scope_type"),
                RoleAssignment.scope_id.label("scope_id"),
                RoleAssignment.created_at.label("created_at"),
                principal_display_name,
                principal_email,
                principal_slug,
            )
            .select_from(RoleAssignment)
            .join(Role, Role.id == RoleAssignment.role_id)
            .outerjoin(
                User,
                and_(
                    RoleAssignment.principal_type == PrincipalType.USER,
                    User.id == RoleAssignment.principal_id,
                ),
            )
            .outerjoin(
                Group,
                and_(
                    RoleAssignment.principal_type == PrincipalType.GROUP,
                    Group.id == RoleAssignment.principal_id,
                ),
            )
            .where(_assignment_scope_filter_v2(scope_type=scope_type, scope_id=scope_id))
        )
        stmt = apply_principal_assignment_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )

        return paginate_query_cursor(
            self._session,
            stmt,
            resolved_sort=resolved_sort,
            limit=limit,
            cursor=cursor,
            include_total=include_total,
            changes_cursor="0",
            row_mapper=_map_principal_assignment_row,
        )

    def get_principal_assignment(self, *, assignment_id: UUID) -> RoleAssignment | None:
        stmt = (
            select(RoleAssignment)
            .options(selectinload(RoleAssignment.workspace))
            .where(RoleAssignment.id == assignment_id)
            .limit(1)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def get_principal_identity(
        self,
        *,
        principal_type: PrincipalType,
        principal_id: UUID,
    ) -> tuple[str | None, str | None, str | None]:
        if principal_type == PrincipalType.USER:
            user = self._session.get(User, principal_id)
            if user is None:
                return (None, None, None)
            return (user.display_name or user.email, user.email, None)

        group = self._session.get(Group, principal_id)
        if group is None:
            return (None, None, None)
        return (group.display_name, None, group.slug)

    def get_principal_assignment_for_scope(
        self,
        *,
        principal_type: PrincipalType,
        principal_id: UUID,
        role_id: UUID,
        scope_type: AssignmentScopeType,
        scope_id: UUID | None,
    ) -> RoleAssignment | None:
        stmt = (
            select(RoleAssignment)
            .where(
                RoleAssignment.principal_type == principal_type,
                RoleAssignment.principal_id == principal_id,
                RoleAssignment.role_id == role_id,
                _assignment_scope_filter_v2(scope_type=scope_type, scope_id=scope_id),
            )
            .limit(1)
        )
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def assign_principal_role_if_missing(
        self,
        *,
        principal_type: PrincipalType,
        principal_id: UUID,
        role_id: UUID,
        scope_type: AssignmentScopeType,
        scope_id: UUID | None,
    ) -> RoleAssignment:
        existing = self.get_principal_assignment_for_scope(
            principal_type=principal_type,
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        if existing is not None:
            return existing
        return self.assign_principal_role(
            principal_type=principal_type,
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def assign_principal_role(
        self,
        *,
        principal_type: PrincipalType,
        principal_id: UUID,
        role_id: UUID,
        scope_type: AssignmentScopeType,
        scope_id: UUID | None,
    ) -> RoleAssignment:
        role = self.get_role(role_id)
        if role is None:
            raise RoleNotFoundError("Role not found")

        expected_scope = (
            ScopeType.WORKSPACE
            if scope_type == AssignmentScopeType.WORKSPACE
            else ScopeType.GLOBAL
        )
        if not role_allows_scope(role.slug, expected_scope):
            raise ScopeMismatchError("Role cannot be assigned to this scope")

        if principal_type == PrincipalType.USER:
            if self._session.get(User, principal_id) is None:
                raise AssignmentError("User not found")
        elif principal_type == PrincipalType.GROUP:
            group = self._session.get(Group, principal_id)
            if group is None:
                raise AssignmentError("Group not found")
            if group.source == GroupSource.IDP and not self._idp_groups_allowed():
                raise ScopeMismatchError(
                    "Provider-managed groups are SCIM-managed and can only be used "
                    "for role assignment when provisioning mode is SCIM."
                )

        if scope_type == AssignmentScopeType.WORKSPACE:
            if scope_id is None:
                raise ScopeMismatchError("workspace scope requires scope_id")
            if self._session.get(Workspace, scope_id) is None:
                raise AssignmentError("Workspace not found")
        else:
            scope_id = None

        assignment = RoleAssignment(
            principal_type=principal_type,
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        self._session.add(assignment)
        try:
            self._session.flush([assignment])
        except IntegrityError as exc:
            raise RoleConflictError("Assignment already exists") from exc
        return assignment

    def delete_principal_assignment(self, *, assignment_id: UUID) -> None:
        assignment = self.get_principal_assignment(assignment_id=assignment_id)
        if assignment is None:
            raise AssignmentNotFoundError("Role assignment not found")
        self._session.delete(assignment)
        self._session.flush()

    def _count_assignments_for_role(self, *, role_id: UUID) -> int:
        legacy_stmt = (
            select(func.count())
            .select_from(UserRoleAssignment)
            .where(UserRoleAssignment.role_id == role_id)
        )
        legacy = int(self._session.execute(legacy_stmt).scalar_one() or 0)
        v2_stmt = (
            select(func.count())
            .select_from(RoleAssignment)
            .where(RoleAssignment.role_id == role_id)
        )
        v2 = int(self._session.execute(v2_stmt).scalar_one() or 0)
        return max(legacy, v2)

    def has_assignments_for_role(
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
        result = self._session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return True
        scope_type = (
            AssignmentScopeType.WORKSPACE
            if workspace_id is not None
            else AssignmentScopeType.ORGANIZATION
        )
        stmt_v2 = (
            select(RoleAssignment.id)
            .where(
                RoleAssignment.role_id == role_id,
                _assignment_scope_filter_v2(scope_type=scope_type, scope_id=workspace_id),
            )
            .limit(1)
        )
        return self._session.execute(stmt_v2).scalar_one_or_none() is not None

    # ------------- permission evaluation ---------

    def get_global_permissions_for_user(self, *, user: User) -> frozenset[str]:
        if user.is_service_account or not user.is_active:
            return frozenset()

        cache_key = ("global_permissions", str(user.id))
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        stmt: Select[tuple[str]] = (
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
        legacy = set(self._session.execute(stmt).scalars().all())

        stmt_v2_user: Select[tuple[str]] = (
            select(Permission.key)
            .select_from(RolePermission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .where(
                RoleAssignment.principal_type == PrincipalType.USER,
                RoleAssignment.principal_id == user.id,
                RoleAssignment.scope_type == AssignmentScopeType.ORGANIZATION,
                Permission.scope_type == ScopeType.GLOBAL,
            )
        )
        from_user_assignments = set(self._session.execute(stmt_v2_user).scalars().all())

        stmt_v2_group: Select[tuple[str]] = (
            select(Permission.key)
            .select_from(RolePermission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .join(
                GroupMembership,
                and_(
                    GroupMembership.group_id == RoleAssignment.principal_id,
                    GroupMembership.user_id == user.id,
                ),
            )
            .join(Group, Group.id == GroupMembership.group_id)
            .where(
                RoleAssignment.principal_type == PrincipalType.GROUP,
                RoleAssignment.scope_type == AssignmentScopeType.ORGANIZATION,
                Group.is_active == true(),
                self._group_source_filter(),
                Permission.scope_type == ScopeType.GLOBAL,
            )
        )
        from_group_assignments = set(self._session.execute(stmt_v2_group).scalars().all())

        granted = frozenset(legacy.union(from_user_assignments).union(from_group_assignments))
        expanded = _expand_implications(granted, scope=ScopeType.GLOBAL)
        self._set_cached(cache_key, expanded)
        return expanded

    def get_workspace_permissions_for_user(
        self,
        *,
        user: User,
        workspace_id: UUID,
    ) -> frozenset[str]:
        if user.is_service_account or not user.is_active:
            return frozenset()

        cache_key = ("workspace_permissions", str(user.id), str(workspace_id))
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        stmt: Select[tuple[str]] = (
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
        legacy = set(self._session.execute(stmt).scalars().all())

        stmt_v2_user: Select[tuple[str]] = (
            select(Permission.key)
            .select_from(RolePermission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .where(
                RoleAssignment.principal_type == PrincipalType.USER,
                RoleAssignment.principal_id == user.id,
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
                Permission.scope_type == ScopeType.WORKSPACE,
            )
        )
        from_user_assignments = set(self._session.execute(stmt_v2_user).scalars().all())

        stmt_v2_group: Select[tuple[str]] = (
            select(Permission.key)
            .select_from(RolePermission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .join(
                GroupMembership,
                and_(
                    GroupMembership.group_id == RoleAssignment.principal_id,
                    GroupMembership.user_id == user.id,
                ),
            )
            .join(Group, Group.id == GroupMembership.group_id)
            .where(
                RoleAssignment.principal_type == PrincipalType.GROUP,
                RoleAssignment.scope_type == AssignmentScopeType.WORKSPACE,
                RoleAssignment.scope_id == workspace_id,
                Group.is_active == true(),
                self._group_source_filter(),
                Permission.scope_type == ScopeType.WORKSPACE,
            )
        )
        from_group_assignments = set(self._session.execute(stmt_v2_group).scalars().all())

        granted = frozenset(legacy.union(from_user_assignments).union(from_group_assignments))
        expanded = _expand_implications(granted, scope=ScopeType.WORKSPACE)

        # Global override: workspaces.manage_all grants all workspace permissions
        global_permissions = self.get_global_permissions_for_user(user=user)
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

    def authorize(
        self,
        *,
        user: User,
        permission_key: str,
        workspace_id: UUID | None = None,
    ) -> AuthorizationDecision:
        normalized = _normalize_permission_key(permission_key)
        definition = PERMISSION_REGISTRY[normalized]
        required = (normalized,)

        if definition.scope_type == ScopeType.GLOBAL:
            granted = self.get_global_permissions_for_user(user=user)
            missing = tuple(sorted(set(required) - granted))
            return AuthorizationDecision(granted=granted, required=required, missing=missing)

        # Workspace-scoped
        if workspace_id is None:
            raise AuthorizationError("workspace_id is required for workspace permissions")

        workspace_permissions = self.get_workspace_permissions_for_user(
            user=user,
            workspace_id=workspace_id,
        )
        missing = tuple(sorted(set(required) - workspace_permissions))
        return AuthorizationDecision(
            granted=workspace_permissions,
            required=required,
            missing=missing,
        )

    def get_global_role_slugs_for_user(self, *, user: User) -> frozenset[str]:
        if user.is_service_account or not user.is_active:
            return frozenset()

        cache_key = ("global_role_slugs", str(user.id))
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        stmt_legacy: Select[tuple[str]] = (
            select(Role.slug)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.workspace_id.is_(None),
            )
        )
        legacy = set(self._session.execute(stmt_legacy).scalars().all())

        stmt_v2_user: Select[tuple[str]] = (
            select(Role.slug)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .where(
                RoleAssignment.principal_type == PrincipalType.USER,
                RoleAssignment.principal_id == user.id,
                RoleAssignment.scope_type == AssignmentScopeType.ORGANIZATION,
            )
        )
        from_user_assignments = set(self._session.execute(stmt_v2_user).scalars().all())

        stmt_v2_group: Select[tuple[str]] = (
            select(Role.slug)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .join(
                GroupMembership,
                and_(
                    GroupMembership.group_id == RoleAssignment.principal_id,
                    GroupMembership.user_id == user.id,
                ),
            )
            .join(Group, Group.id == GroupMembership.group_id)
            .where(
                RoleAssignment.principal_type == PrincipalType.GROUP,
                RoleAssignment.scope_type == AssignmentScopeType.ORGANIZATION,
                Group.is_active == true(),
                self._group_source_filter(),
            )
        )
        from_group_assignments = set(self._session.execute(stmt_v2_group).scalars().all())

        slugs = frozenset(legacy.union(from_user_assignments).union(from_group_assignments))
        self._set_cached(cache_key, slugs)
        return slugs

    # Convenience wrappers for dependencies / routers ------------------

    def has_permission_for_user_id(
        self,
        *,
        user_id: UUID,
        permission_key: str,
        workspace_id: UUID | None = None,
    ) -> bool:
        user = self._session.get(User, user_id)
        if user is None:
            return False
        decision = self.authorize(
            user=user,
            permission_key=permission_key,
            workspace_id=workspace_id,
        )
        return not decision.missing


# Convenience function if you ever need it outside of dependency wiring
def authorize(
    *,
    session: Session,
    user: User,
    permission_key: str,
    workspace_id: UUID | None = None,
) -> AuthorizationDecision:
    service = RbacService(session=session)
    return service.authorize(
        user=user,
        permission_key=permission_key,
        workspace_id=workspace_id,
    )
