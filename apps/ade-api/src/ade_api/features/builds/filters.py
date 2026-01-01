from __future__ import annotations

from sqlalchemy.sql import Select

from ade_api.common.list_filters import (
    FilterField,
    FilterItem,
    FilterJoinOperator,
    FilterOperator,
    FilterRegistry,
    FilterValueType,
    build_predicate,
    combine_predicates,
    prepare_filters,
)
from ade_api.common.search import build_q_predicate
from ade_api.features.search_registry import SEARCH_REGISTRY
from ade_api.models import Build, BuildStatus

BUILD_FILTER_REGISTRY = FilterRegistry(
    [
        FilterField(
            id="status",
            column=Build.status,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.IN,
                FilterOperator.NOT_IN,
            },
            value_type=FilterValueType.ENUM,
            enum_type=BuildStatus,
        ),
        FilterField(
            id="createdAt",
            column=Build.created_at,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.BETWEEN,
            },
            value_type=FilterValueType.DATETIME,
        ),
        FilterField(
            id="startedAt",
            column=Build.started_at,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.BETWEEN,
                FilterOperator.IS_EMPTY,
                FilterOperator.IS_NOT_EMPTY,
            },
            value_type=FilterValueType.DATETIME,
        ),
        FilterField(
            id="finishedAt",
            column=Build.finished_at,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.BETWEEN,
                FilterOperator.IS_EMPTY,
                FilterOperator.IS_NOT_EMPTY,
            },
            value_type=FilterValueType.DATETIME,
        ),
    ]
)


def apply_build_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed_filters = prepare_filters(filters, BUILD_FILTER_REGISTRY)
    predicates: list = [build_predicate(parsed) for parsed in parsed_filters]

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    q_predicate = build_q_predicate(resource="builds", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)

    return stmt


__all__ = ["BUILD_FILTER_REGISTRY", "apply_build_filters"]
