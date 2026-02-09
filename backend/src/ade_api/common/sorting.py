from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, TypeVar

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


def _parse_json_sort(raw: str) -> list[str]:
    trimmed = raw.strip()
    if not trimmed:
        return []
    try:
        decoded = json.loads(trimmed)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="sort must be valid JSON",
        ) from exc
    if isinstance(decoded, dict):
        decoded = [decoded]
    if not isinstance(decoded, list):
        raise HTTPException(status_code=422, detail="sort must be a JSON array")
    tokens: list[str] = []
    for index, item in enumerate(decoded):
        if isinstance(item, str):
            token = item.strip()
            if token:
                tokens.append(token)
            continue
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=422,
                detail=f"Sort #{index + 1} must be an object",
            )
        raw_id = item.get("id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise HTTPException(
                status_code=422,
                detail=f"Sort #{index + 1} must include a non-empty 'id'",
            )
        desc = item.get("desc", False)
        if not isinstance(desc, bool):
            raise HTTPException(
                status_code=422,
                detail=f"Sort #{index + 1} 'desc' must be a boolean",
            )
        name = raw_id.strip()
        tokens.append(f"-{name}" if desc else name)
    return tokens


def parse_sort(raw: str | None) -> list[str]:
    """Normalise the raw `sort` query parameter into canonical tokens."""

    if not raw:
        return []

    tokens = _parse_json_sort(raw)
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


T = TypeVar("T")


def sort_sequence(
    items: Sequence[T],
    tokens: Iterable[str],
    *,
    allowed: Mapping[str, Callable[[T], Any]],
    default: Sequence[str],
    id_key: Callable[[T], Any],
) -> list[T]:
    materialized = list(tokens) or list(default)
    if not materialized:
        raise HTTPException(status_code=422, detail="No sort tokens provided.")

    parsed: list[tuple[Callable[[T], Any], bool]] = []
    names: list[str] = []
    first_desc: bool | None = None

    for token in materialized:
        descending = token.startswith("-")
        name = token[1:] if descending else token
        names.append(name)
        key_fn = allowed.get(name)
        if key_fn is None:
            allowed_list = ", ".join(sorted(allowed.keys()))
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported sort field '{name}'. Allowed: {allowed_list}",
            )
        parsed.append((key_fn, descending))
        if first_desc is None:
            first_desc = descending

    if "id" not in names:
        parsed.append((id_key, bool(first_desc)))

    ordered = list(items)
    for key_fn, descending in reversed(parsed):
        ordered.sort(key=key_fn, reverse=descending)
    return ordered


def make_sort_dependency(*, allowed: SortAllowedMap, default: Sequence[str], id_field):
    """Return a FastAPI dependency that parses and resolves sort tokens."""

    allowed_list = ", ".join(sorted(allowed.keys()))
    doc = (
        "JSON array of {id, desc}. "
        f'Allowed: {allowed_list}. Example: [{{"id":"createdAt","desc":true}}]'
    )

    def dependency(sort: str | None = Query(None, description=doc)) -> OrderBy:
        tokens = parse_sort(sort)
        return resolve_sort(tokens, allowed=allowed, default=default, id_field=id_field)

    return dependency


__all__ = ["make_sort_dependency", "parse_sort", "resolve_sort", "sort_sequence"]
