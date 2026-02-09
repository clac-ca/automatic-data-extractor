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
from ade_api.models import User

USER_FILTER_REGISTRY = FilterRegistry(
    [
        FilterField(
            id="isActive",
            column=User.is_active,
            operators={FilterOperator.EQ, FilterOperator.NE},
            value_type=FilterValueType.BOOL,
        ),
        FilterField(
            id="isServiceAccount",
            column=User.is_service_account,
            operators={FilterOperator.EQ, FilterOperator.NE},
            value_type=FilterValueType.BOOL,
        ),
        FilterField(
            id="createdAt",
            column=User.created_at,
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
            id="lastLoginAt",
            column=User.last_login_at,
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
            id="failedLoginCount",
            column=User.failed_login_count,
            operators={
                FilterOperator.EQ,
                FilterOperator.NE,
                FilterOperator.LT,
                FilterOperator.LTE,
                FilterOperator.GT,
                FilterOperator.GTE,
                FilterOperator.BETWEEN,
                FilterOperator.IN,
                FilterOperator.NOT_IN,
            },
            value_type=FilterValueType.INT,
        ),
    ]
)


def apply_user_filters(
    stmt: Select,
    filters: list[FilterItem],
    *,
    join_operator: FilterJoinOperator,
    q: str | None,
) -> Select:
    parsed_filters = prepare_filters(filters, USER_FILTER_REGISTRY)
    predicates: list = [build_predicate(parsed) for parsed in parsed_filters]

    combined = combine_predicates(predicates, join_operator)
    if combined is not None:
        stmt = stmt.where(combined)

    q_predicate = build_q_predicate(resource="users", q=q, registry=SEARCH_REGISTRY)
    if q_predicate is not None:
        stmt = stmt.where(q_predicate)
    return stmt


__all__ = ["USER_FILTER_REGISTRY", "apply_user_filters"]
