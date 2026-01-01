"""Shared helpers for free-text search query parsing."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement

MAX_QUERY_LENGTH = 200
MAX_QUERY_TOKENS = 8
MIN_QUERY_TOKEN_LENGTH = 2
LIKE_ESCAPE = "\\"


@dataclass(frozen=True)
class ParsedQuery:
    normalized: str | None
    tokens: Sequence[str]


@dataclass(frozen=True)
class SearchField:
    id: str
    predicate: Callable[[str], ColumnElement[object]]


class SearchRegistry:
    def __init__(self, entries: dict[str, Sequence[SearchField]]) -> None:
        self._entries = {key: tuple(value) for key, value in entries.items()}

    def get(self, key: str) -> Sequence[SearchField] | None:
        return self._entries.get(key)

    def keys(self) -> Sequence[str]:
        return tuple(self._entries.keys())


def normalize_q(q: str | None) -> str | None:
    if q is None:
        return None
    candidate = " ".join(q.strip().split())
    return candidate or None


def tokenize_q(q: str | None) -> list[str]:
    normalized = normalize_q(q)
    if not normalized:
        return []
    tokens = normalized.split()
    return [token for token in tokens if len(token) >= MIN_QUERY_TOKEN_LENGTH]


def parse_q(q: str | None) -> ParsedQuery:
    normalized = normalize_q(q)
    if normalized and len(normalized) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"q exceeds {MAX_QUERY_LENGTH} characters",
        )
    tokens = tokenize_q(normalized)
    if len(tokens) > MAX_QUERY_TOKENS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Too many q tokens (max {MAX_QUERY_TOKENS}).",
        )
    return ParsedQuery(normalized=normalized, tokens=tokens)


def escape_like(token: str) -> str:
    return (
        token.replace(LIKE_ESCAPE, LIKE_ESCAPE + LIKE_ESCAPE)
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )


def build_like_predicate(column: ColumnElement[object]) -> Callable[[str], ColumnElement[object]]:
    def _predicate(token: str) -> ColumnElement[object]:
        escaped = escape_like(token)
        pattern = f"%{escaped}%"
        return column.ilike(pattern, escape=LIKE_ESCAPE)

    return _predicate


def build_q_predicate(
    *,
    resource: str,
    q: str | None,
    registry: SearchRegistry,
) -> ColumnElement[object] | None:
    parsed = parse_q(q)
    if not parsed.tokens:
        return None

    fields = registry.get(resource)
    if not fields:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"q is not supported for resource '{resource}'.",
        )

    token_predicates: list[ColumnElement[object]] = []
    for token in parsed.tokens:
        field_predicates = [field.predicate(token) for field in fields]
        token_predicates.append(or_(*field_predicates))
    return and_(*token_predicates)


def matches_q_values(q: str | None, values: Iterable[str | None]) -> bool:
    parsed = parse_q(q)
    return matches_tokens(parsed.tokens, values)


def matches_tokens(tokens: Sequence[str], values: Iterable[str | None]) -> bool:
    if not tokens:
        return True
    normalized = [value.lower() for value in values if value]
    for token in tokens:
        token_value = token.lower()
        if not any(token_value in candidate for candidate in normalized):
            return False
    return True


__all__ = [
    "LIKE_ESCAPE",
    "MAX_QUERY_LENGTH",
    "MAX_QUERY_TOKENS",
    "MIN_QUERY_TOKEN_LENGTH",
    "ParsedQuery",
    "SearchField",
    "SearchRegistry",
    "build_like_predicate",
    "build_q_predicate",
    "escape_like",
    "matches_q_values",
    "matches_tokens",
    "normalize_q",
    "parse_q",
    "tokenize_q",
]
