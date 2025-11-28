from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.sql import operators


def reselect_distinct_by_pk(stmt, *, entity, pk_col):
    """Return a statement selecting distinct primary keys before pagination."""

    ids = stmt.with_only_columns(pk_col).distinct().order_by(None).subquery()
    return select(entity).join(ids, ids.c[pk_col.key] == pk_col)


def nulls_last(ordering):
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
