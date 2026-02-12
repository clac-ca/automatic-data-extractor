from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import true
from sqlalchemy.sql import Select

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
from ade_api.common.search import build_q_predicate, matches_tokens, parse_q
from ade_api.core.rbac.registry import role_allows_scope
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


def parse_role_filters(filters: list[FilterItem]) -> list[ParsedFilter]:
    return prepare_filters(filters, ROLE_FILTER_REGISTRY)


def evaluate_role_filters(
    role: Role,
    parsed_filters: Sequence[ParsedFilter],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> bool:
    results: list[bool] = []

    for parsed in parsed_filters:
        filter_id = parsed.field.id
        operator = parsed.operator
        value = parsed.value

        if filter_id == "scopeType":
            values = value if isinstance(value, list) else [value]
            scopes = {ScopeType(item) if isinstance(item, str) else item for item in values}
            match = any(role_allows_scope(role.slug, scope) for scope in scopes)
            if operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
                match = not match
            results.append(match)
            continue

        if filter_id == "name":
            match = _match_text(role.name, value, operator)
            results.append(match)
            continue

        if filter_id == "slug":
            match = _match_text(role.slug, value, operator)
            results.append(match)
            continue

        if filter_id == "isSystem":
            match = role.is_system == bool(value)
            if operator == FilterOperator.NE:
                match = not match
            results.append(match)
            continue

        if filter_id == "isEditable":
            match = role.is_editable == bool(value)
            if operator == FilterOperator.NE:
                match = not match
            results.append(match)
            continue

    if q:
        tokens = parse_q(q).tokens
        values = [role.name, role.slug, role.description]
        results.append(matches_tokens(tokens, values))

    return _combine_results(results, join_operator)


def _match_text(text: str, value: object, operator: FilterOperator) -> bool:
    source = (text or "").lower()
    if operator in {FilterOperator.EQ, FilterOperator.NE}:
        match = source == str(value or "").lower()
        return not match if operator == FilterOperator.NE else match
    match = str(value or "").lower() in source
    if operator == FilterOperator.NOT_ILIKE:
        match = not match
    return match


def _combine_results(results: Sequence[bool], join_operator: FilterJoinOperator) -> bool:
    if not results:
        return True
    if join_operator == FilterJoinOperator.OR:
        return any(results)
    return all(results)


__all__ = [
    "ASSIGNMENT_FILTER_REGISTRY",
    "PRINCIPAL_ASSIGNMENT_FILTER_REGISTRY",
    "PERMISSION_FILTER_REGISTRY",
    "ROLE_FILTER_REGISTRY",
    "apply_assignment_filters",
    "apply_principal_assignment_filters",
    "apply_permission_filters",
    "evaluate_role_filters",
    "parse_role_filters",
]
