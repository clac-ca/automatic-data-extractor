from __future__ import annotations

from typing import Any


COMMON_NAME_HEADERS = {
    "name",
    "full name",
    "member name",
    "customer name",
}


def detect_header_keywords(
    *,
    header: str,
    values: list[Any],
    column_index: int,
    table: dict[str, Any],
    job_context: dict[str, Any],
    env: dict[str, str],
) -> dict[str, float]:
    if header and header.lower().strip() in COMMON_NAME_HEADERS:
        return {"scores": {"self": 1.2}}
    return {"scores": {}}


def detect_presence_of_space(
    *,
    header: str,
    values: list[Any],
    column_index: int,
    table: dict[str, Any],
    job_context: dict[str, Any],
    env: dict[str, str],
) -> dict[str, float]:
    sample = [str(value) for value in values[:50] if value not in (None, "")]
    if not sample:
        return {"scores": {}}
    spaced = [value for value in sample if " " in value.strip()]
    if not spaced:
        return {"scores": {}}
    coverage = len(spaced) / len(sample)
    return {"scores": {"self": min(coverage * 1.0, 1.0)}}


def transform(
    *,
    header: str,
    values: list[Any],
    column_index: int,
    table: dict[str, Any],
    job_context: dict[str, Any],
    env: dict[str, str],
) -> dict[str, Any]:
    locale = job_context.get("locale", env.get("LOCALE", "en-CA"))
    normalized: list[str | None] = []
    for value in values:
        if value in (None, ""):
            normalized.append(None)
            continue
        text = " ".join(str(value).strip().split())
        if not text:
            normalized.append(None)
            continue
        normalized.append(text.title() if locale.startswith("en") else text)
    return {"values": normalized, "warnings": []}
