from __future__ import annotations

from sqlalchemy import select


def reselect_distinct_by_pk(stmt, *, entity, pk_col):
    """Return a statement selecting distinct primary keys before pagination."""

    ids = stmt.with_only_columns(pk_col).distinct().order_by(None).subquery()
    return select(entity).join(ids, ids.c[pk_col.key] == pk_col)


def nulls_last(ordering):
    """Apply ``NULLS LAST`` when supported by the active dialect."""

    try:
        return ordering.nulls_last()
    except AttributeError:
        return ordering


__all__ = ["reselect_distinct_by_pk", "nulls_last"]
