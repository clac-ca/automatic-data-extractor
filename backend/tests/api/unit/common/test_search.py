from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import column
from sqlalchemy.dialects import postgresql

from ade_api.common.search import (
    MAX_QUERY_LENGTH,
    MAX_QUERY_TOKENS,
    SearchField,
    SearchRegistry,
    build_like_predicate,
    build_q_predicate,
    escape_like,
    normalize_q,
    parse_q,
    tokenize_q,
)


def test_normalize_q_trims_and_collapses_whitespace() -> None:
    assert normalize_q(None) is None
    assert normalize_q("   ") is None
    assert normalize_q("  acme   invoice ") == "acme invoice"
    assert normalize_q("acme\tinvoice\nreport") == "acme invoice report"


def test_tokenize_q_drops_single_character_tokens() -> None:
    assert tokenize_q("a bc d ef") == ["bc", "ef"]
    assert tokenize_q("x y") == []


def test_parse_q_rejects_overlong_queries() -> None:
    raw = "a" * (MAX_QUERY_LENGTH + 1)
    with pytest.raises(HTTPException):
        parse_q(raw)


def test_parse_q_rejects_too_many_tokens() -> None:
    tokens = " ".join(f"t{idx}" for idx in range(MAX_QUERY_TOKENS + 1))
    with pytest.raises(HTTPException):
        parse_q(tokens)


def test_parse_q_allows_short_tokens_to_drop_under_limit() -> None:
    tokens = " ".join(["a"] * (MAX_QUERY_TOKENS + 2))
    parsed = parse_q(tokens)
    assert parsed.tokens == []


def test_escape_like_escapes_wildcards_and_backslashes() -> None:
    assert escape_like(r"100%_done\path") == r"100\%\_done\\path"


def test_build_q_predicate_and_or_tokens() -> None:
    registry = SearchRegistry(
        {
            "test": [
                SearchField("name", build_like_predicate(column("name"))),
                SearchField("code", build_like_predicate(column("code"))),
            ]
        }
    )

    predicate = build_q_predicate(resource="test", q="alpha beta", registry=registry)
    compiled = predicate.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "AND" in sql
    assert "OR" in sql
