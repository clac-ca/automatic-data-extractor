from __future__ import annotations

from collections.abc import Sequence

from ade_api.common.list_filters import (
    FilterField,
    FilterItem,
    FilterJoinOperator,
    FilterOperator,
    FilterRegistry,
    FilterValueType,
    ParsedFilter,
    prepare_filters,
)
from ade_api.common.search import matches_tokens, parse_q
from ade_api.models import UserRoleAssignment, Workspace

from .schemas import WorkspaceOut

WORKSPACE_FILTER_REGISTRY = FilterRegistry(
    [
        FilterField(
            id="name",
            column=Workspace.name,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.NOT_IN,
                FilterOperator.ILIKE,
                FilterOperator.NOT_ILIKE,
            },
            value_type=FilterValueType.STRING,
        ),
        FilterField(
            id="slug",
            column=Workspace.slug,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.NOT_IN,
                FilterOperator.ILIKE,
                FilterOperator.NOT_ILIKE,
            },
            value_type=FilterValueType.STRING,
        ),
        FilterField(
            id="isDefault",
            column=Workspace.id,
            operators={FilterOperator.EQ, FilterOperator.NE},
            value_type=FilterValueType.BOOL,
        ),
        FilterField(
            id="processingPaused",
            column=Workspace.id,
            operators={FilterOperator.EQ, FilterOperator.NE},
            value_type=FilterValueType.BOOL,
        ),
    ]
)

WORKSPACE_MEMBER_FILTER_REGISTRY = FilterRegistry(
    [
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
            id="isActive",
            column=UserRoleAssignment.user_id,
            operators={FilterOperator.EQ, FilterOperator.NE},
            value_type=FilterValueType.BOOL,
        ),
    ]
)


def parse_workspace_filters(filters: list[FilterItem]) -> list[ParsedFilter]:
    return prepare_filters(filters, WORKSPACE_FILTER_REGISTRY)


def parse_workspace_member_filters(filters: list[FilterItem]) -> list[ParsedFilter]:
    return prepare_filters(filters, WORKSPACE_MEMBER_FILTER_REGISTRY)


def evaluate_workspace_filters(
    item: WorkspaceOut,
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

        if filter_id == "name":
            match = _match_text(item.name, value, operator)
        elif filter_id == "slug":
            match = _match_text(item.slug or "", value, operator)
        elif filter_id == "isDefault":
            match = item.is_default == bool(value)
            if operator == FilterOperator.NE:
                match = not match
        elif filter_id == "processingPaused":
            match = item.processing_paused == bool(value)
            if operator == FilterOperator.NE:
                match = not match
        else:  # pragma: no cover - registry ensures ids are known
            match = True

        results.append(match)

    if q:
        tokens = parse_q(q).tokens
        results.append(matches_tokens(tokens, [item.name, item.slug]))

    return _combine_results(results, join_operator)


def evaluate_member_filters(
    assignments: Sequence[UserRoleAssignment],
    parsed_filters: Sequence[ParsedFilter],
    *,
    join_operator: FilterJoinOperator,
) -> bool:
    if not assignments:
        return False
    user = assignments[0].user
    user_id = assignments[0].user_id
    role_ids = {assignment.role_id for assignment in assignments}
    is_active = bool(getattr(user, "is_active", True)) if user is not None else True

    results: list[bool] = []
    for parsed in parsed_filters:
        filter_id = parsed.field.id
        operator = parsed.operator
        value = parsed.value

        if filter_id == "userId":
            values = value if isinstance(value, list) else [value]
            user_values = {str(item) for item in values}
            match = str(user_id) in user_values
            if operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
                match = not match
            results.append(match)
            continue

        if filter_id == "roleId":
            values = value if isinstance(value, list) else [value]
            role_values = {str(item) for item in values}
            match = any(str(role_id) in role_values for role_id in role_ids)
            if operator in {FilterOperator.NE, FilterOperator.NOT_IN}:
                match = not match
            results.append(match)
            continue

        if filter_id == "isActive":
            match = is_active == bool(value)
            if operator == FilterOperator.NE:
                match = not match
            results.append(match)
            continue

    return _combine_results(results, join_operator)


def _match_text(text: str, value: object, operator: FilterOperator) -> bool:
    source = (text or "").lower()
    if operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
        values = value if isinstance(value, list) else [value]
        candidates = {str(item).lower() for item in values}
        match = source in candidates
        return not match if operator == FilterOperator.NOT_IN else match
    if operator in {FilterOperator.EQ, FilterOperator.NE}:
        match = source == str(value or "").lower()
        return not match if operator == FilterOperator.NE else match

    # Treat ILIKE as case-insensitive substring.
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
    "WORKSPACE_FILTER_REGISTRY",
    "WORKSPACE_MEMBER_FILTER_REGISTRY",
    "evaluate_member_filters",
    "evaluate_workspace_filters",
    "parse_workspace_filters",
    "parse_workspace_member_filters",
]
