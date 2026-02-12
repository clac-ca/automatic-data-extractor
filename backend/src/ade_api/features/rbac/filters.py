from __future__ import annotations

from sqlalchemy import not_, or_, true
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from ade_api.common.list_filters import (
    FilterField,
    FilterItem,
    FilterJoinOperator,
    FilterOperator,
    FilterRegistry,
    FilterValueType,
    ParsedFilter,
    build_predicate,
    combine_predicates,
    prepare_filters,
)
from ade_api.common.search import build_q_predicate
from ade_api.core.rbac.registry import SYSTEM_ROLE_BY_SLUG, role_allows_scope
from ade_api.core.rbac.types import ScopeType
from ade_api.features.search_registry import SEARCH_REGISTRY
from ade_db.models import (
    AssignmentScopeType,
    Permission,
    PrincipalType,
    Role,
    RoleAssignment,
    User,
    UserRoleAssignment,
)

PERMISSION_FILTER_REGISTRY = FilterRegistry([
    FilterField(
        id="scopeType",
        column=Permission.scope_type,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.ENUM,
        enum_type=ScopeType,
    ),
    FilterField(
        id="key",
        column=Permission.key,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="resource",
        column=Permission.resource,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="action",
        column=Permission.action,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="label",
        column=Permission.label,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
        },
        value_type=FilterValueType.STRING,
    ),
])

ROLE_FILTER_REGISTRY = FilterRegistry([
    FilterField(
        id="scopeType",
        column=Role.id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.ENUM,
        enum_type=ScopeType,
    ),
    FilterField(
        id="name",
        column=Role.name,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="slug",
        column=Role.slug,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="isSystem",
        column=Role.is_system,
        operators={FilterOperator.EQ, FilterOperator.NE},
        value_type=FilterValueType.BOOL,
    ),
    FilterField(
        id="isEditable",
        column=Role.is_editable,
        operators={FilterOperator.EQ, FilterOperator.NE},
        value_type=FilterValueType.BOOL,
    ),
])

ASSIGNMENT_FILTER_REGISTRY = FilterRegistry([
    FilterField(
        id="userId",
        column=UserRoleAssignment.user_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="roleId",
        column=UserRoleAssignment.role_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="scopeId",
        column=UserRoleAssignment.workspace_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="isActive",
        column=User.is_active,
        operators={FilterOperator.EQ, FilterOperator.NE},
        value_type=FilterValueType.BOOL,
    ),
])

PRINCIPAL_ASSIGNMENT_FILTER_REGISTRY = FilterRegistry([
    FilterField(
        id="principalType",
        column=RoleAssignment.principal_type,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.ENUM,
        enum_type=PrincipalType,
    ),
    FilterField(
        id="principalId",
        column=RoleAssignment.principal_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="roleId",
        column=RoleAssignment.role_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.UUID,
    ),
    FilterField(
        id="roleSlug",
        column=Role.slug,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="scopeType",
        column=RoleAssignment.scope_type,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.ENUM,
        enum_type=AssignmentScopeType,
    ),
    FilterField(
        id="scopeId",
        column=RoleAssignment.scope_id,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
            FilterOperator.IS_EMPTY,
            FilterOperator.IS_NOT_EMPTY,
        },
        value_type=FilterValueType.UUID,
    ),
])


def apply_permission_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed = prepare_filters(filters, PERMISSION_FILTER_REGISTRY)
    predicates: list = [build_predicate(item) for item in parsed]

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    q_predicate = build_q_predicate(resource="permissions", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)
    return stmt


def apply_assignment_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
    default_active_only: bool = True,
) -> Select:
    parsed = prepare_filters(filters, ASSIGNMENT_FILTER_REGISTRY)
    predicates: list = []
    needs_user_join = any(item.field.id == "isActive" for item in parsed)

    if default_active_only and not needs_user_join:
        stmt = stmt.join(User, UserRoleAssignment.user).where(User.is_active == true())
        default_active_only = False

    for item in parsed:
        if item.field.id == "isActive":
            needs_user_join = True
        predicates.append(build_predicate(item))

    if needs_user_join:
        stmt = stmt.join(User, UserRoleAssignment.user)

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    q_predicate = build_q_predicate(resource="roleassignments", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)
    return stmt


def apply_principal_assignment_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed = prepare_filters(filters, PRINCIPAL_ASSIGNMENT_FILTER_REGISTRY)
    predicates = [build_predicate(item) for item in parsed]

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    q_predicate = build_q_predicate(
        resource="principalroleassignments",
        q=q,
        registry=SEARCH_REGISTRY,
    )
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)
    return stmt


_SYSTEM_ROLE_SLUGS = tuple(SYSTEM_ROLE_BY_SLUG.keys())


def _role_scope_match_predicate(scope: ScopeType) -> ColumnElement[bool]:
    if not _SYSTEM_ROLE_SLUGS:
        return true()

    allowed_system_slugs = tuple(
        slug for slug in _SYSTEM_ROLE_SLUGS if role_allows_scope(slug, scope)
    )
    custom_role_predicate = Role.slug.notin_(_SYSTEM_ROLE_SLUGS)
    if not allowed_system_slugs:
        return custom_role_predicate
    return or_(custom_role_predicate, Role.slug.in_(allowed_system_slugs))


def _build_role_scope_predicate(parsed: ParsedFilter) -> ColumnElement[bool]:
    raw_value = parsed.value
    values = raw_value if isinstance(raw_value, list) else [raw_value]
    scopes = [
        value if isinstance(value, ScopeType) else ScopeType(value)
        for value in values
    ]
    if not scopes:
        return true()
    matches_any_scope = or_(*(_role_scope_match_predicate(scope) for scope in scopes))
    if parsed.operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
        return not_(matches_any_scope)
    return matches_any_scope


def apply_role_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed = prepare_filters(filters, ROLE_FILTER_REGISTRY)
    predicates: list = []
    for item in parsed:
        if item.field.id == "scopeType":
            predicates.append(_build_role_scope_predicate(item))
            continue
        predicates.append(build_predicate(item))

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    q_predicate = build_q_predicate(resource="roles", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)
    return stmt


__all__ = [
    "ASSIGNMENT_FILTER_REGISTRY",
    "PRINCIPAL_ASSIGNMENT_FILTER_REGISTRY",
    "PERMISSION_FILTER_REGISTRY",
    "ROLE_FILTER_REGISTRY",
    "apply_assignment_filters",
    "apply_principal_assignment_filters",
    "apply_permission_filters",
    "apply_role_filters",
]
