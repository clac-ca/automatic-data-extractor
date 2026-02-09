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
from ade_db.models import Configuration, ConfigurationStatus

CONFIG_FILTER_REGISTRY = FilterRegistry([
    FilterField(
        id="status",
        column=Configuration.status,
        operators={
            FilterOperator.EQ,
            FilterOperator.NE,
            FilterOperator.IN,
            FilterOperator.NOT_IN,
        },
        value_type=FilterValueType.ENUM,
        enum_type=ConfigurationStatus,
    ),
    FilterField(
        id="displayName",
        column=Configuration.display_name,
        operators={
            FilterOperator.EQ,
            FilterOperator.ILIKE,
            FilterOperator.NOT_ILIKE,
        },
        value_type=FilterValueType.STRING,
    ),
    FilterField(
        id="createdAt",
        column=Configuration.created_at,
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
        id="updatedAt",
        column=Configuration.updated_at,
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
        id="activatedAt",
        column=Configuration.activated_at,
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
        id="lastUsedAt",
        column=Configuration.last_used_at,
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
])


def apply_config_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed_filters = prepare_filters(filters, CONFIG_FILTER_REGISTRY)
    predicates: list = [build_predicate(parsed) for parsed in parsed_filters]

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    q_predicate = build_q_predicate(resource="configurations", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)

    return stmt


__all__ = ["CONFIG_FILTER_REGISTRY", "apply_config_filters"]
