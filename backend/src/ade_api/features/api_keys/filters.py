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
from ade_db.models import ApiKey

API_KEY_FILTER_REGISTRY = FilterRegistry([
    FilterField(
        id="revokedAt",
        column=ApiKey.revoked_at,
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
        id="expiresAt",
        column=ApiKey.expires_at,
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
        id="createdAt",
        column=ApiKey.created_at,
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
        id="lastUsedAt",
        column=ApiKey.last_used_at,
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


def apply_api_key_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed_filters = prepare_filters(filters, API_KEY_FILTER_REGISTRY)
    predicates: list = [build_predicate(parsed) for parsed in parsed_filters]
    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)
    q_predicate = build_q_predicate(resource="apikeys", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)
    return stmt


__all__ = ["API_KEY_FILTER_REGISTRY", "apply_api_key_filters"]
