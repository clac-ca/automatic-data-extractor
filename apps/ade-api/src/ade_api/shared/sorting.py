from __future__ import annotations

from collections.abc import Iterable, Sequence

from fastapi import HTTPException, Query

from ade_api.settings import MAX_SORT_FIELDS

from .types import OrderBy, SortAllowedMap


def _dedupe_preserve_order(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def parse_sort(raw: str | None) -> list[str]:
    """Normalise the raw `sort` query parameter into canonical tokens."""

    if not raw:
        return []
    tokens: list[str] = []
    for fragment in raw.split(","):
        token = fragment.strip()
        if not token:
            continue
        descending = token.startswith("-")
        name = (token[1:] if descending else token).strip().lower()
        if not name:
            continue
        tokens.append(f"-{name}" if descending else name)
    tokens = _dedupe_preserve_order(tokens)
    if len(tokens) > MAX_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"Too many sort fields (max {MAX_SORT_FIELDS}).",
        )
    return tokens


def resolve_sort(
    tokens: Iterable[str],
    *,
    allowed: SortAllowedMap,
    default: Sequence[str],
    id_field,
) -> OrderBy:
    """Resolve canonical sort tokens into SQLAlchemy order-by columns."""

    materialized = list(tokens) or list(default)
    if not materialized:
        raise HTTPException(status_code=422, detail="No sort tokens provided.")

    order: list = []
    first_desc: bool | None = None
    names: list[str] = []
    for token in materialized:
        descending = token.startswith("-")
        name = token[1:] if descending else token
        names.append(name)
        columns = allowed.get(name)
        if columns is None:
            allowed_list = ", ".join(sorted(allowed.keys()))
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported sort field '{name}'. Allowed: {allowed_list}",
            )
        chosen = columns[1] if descending else columns[0]
        if isinstance(chosen, (list, tuple)):
            order.extend(chosen)
        else:
            order.append(chosen)
        if first_desc is None:
            first_desc = descending

    if "id" not in names:
        chosen = id_field[1] if first_desc else id_field[0]
        if isinstance(chosen, (list, tuple)):
            order.extend(chosen)
        else:
            order.append(chosen)

    return tuple(order)


def make_sort_dependency(*, allowed: SortAllowedMap, default: Sequence[str], id_field):
    """Return a FastAPI dependency that parses and resolves sort tokens."""

    allowed_list = ", ".join(sorted(allowed.keys()))
    doc = "CSV; prefix '-' for DESC. Allowed: " + allowed_list + ". Example: -created_at,name"

    def dependency(sort: str | None = Query(None, description=doc)) -> OrderBy:
        tokens = parse_sort(sort)
        return resolve_sort(tokens, allowed=allowed, default=default, id_field=id_field)

    return dependency


__all__ = ["make_sort_dependency", "parse_sort", "resolve_sort"]
