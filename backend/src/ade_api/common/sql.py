from __future__ import annotations

from typing import Any

from sqlalchemy import case, select
from sqlalchemy.sql import Select, operators
from sqlalchemy.sql.elements import ColumnElement


def reselect_distinct_by_pk(
    stmt: Select[Any], *, entity: Any, pk_col: ColumnElement[Any]
) -> Select[Any]:
    """Return a statement selecting distinct primary keys before pagination."""

    ids = stmt.with_only_columns(pk_col).distinct().order_by(None).subquery()
    pk_key = pk_col.key
    if pk_key is None:
        raise ValueError("primary key column must expose a key")
    return select(entity).join(ids, ids.c[pk_key] == pk_col)


def nulls_last(ordering: ColumnElement[Any]) -> list[ColumnElement[Any]]:
    """Return a CASE-based ordering that places NULLs last on all dialects."""

    col = getattr(ordering, "element", None)
    if col is None:
        col = getattr(ordering, "expression", None)
    if col is None:
        col = ordering
    is_desc = getattr(ordering, "modifier", None) is operators.desc_op
    null_rank = case((col.is_(None), 1), else_=0)
    ordered_col = col.desc() if is_desc else col.asc()
    return [null_rank, ordered_col]


__all__ = ["reselect_distinct_by_pk", "nulls_last"]
