from __future__ import annotations

from typing import Any


def detect_header_keywords(
    *,
    header: str,
    values: list[Any],
    column_index: int,
    table: dict[str, Any],
    job_context: dict[str, Any],
    env: dict[str, str],
) -> dict[str, float]:
    if not header:
        return {"scores": {}}
    lowered = header.lower()
    if "member" in lowered and "id" in lowered:
        return {"scores": {"self": 1.5}}
    if lowered in {"id", "identifier"}:
        return {"scores": {"self": 0.5}}
    return {"scores": {}}


def detect_value_shape(
    *,
    header: str,
    values: list[Any],
    column_index: int,
    table: dict[str, Any],
    job_context: dict[str, Any],
    env: dict[str, str],
) -> dict[str, float]:
    trimmed = [str(value).strip() for value in values if value not in (None, "")]
    if not trimmed:
        return {"scores": {}}
    alnum = [token for token in trimmed[:50] if token.isalnum()]
    if len(alnum) == len(trimmed[:50]):
        return {"scores": {"self": 0.8}}
    return {"scores": {}}


def transform(
    *,
    header: str,
    values: list[Any],
    column_index: int,
    table: dict[str, Any],
    job_context: dict[str, Any],
    env: dict[str, str],
) -> dict[str, Any]:
    output: list[str | None] = []
    warnings: list[str] = []
    for index, value in enumerate(values):
        if value in (None, ""):
            output.append(None)
            continue
        token = str(value).strip()
        if not token:
            output.append(None)
            continue
        upper = token.upper()
        if not upper.isalnum():
            warnings.append(f"Row {index + 1}: member ID contains unexpected characters.")
        output.append(upper)
    return {"values": output, "warnings": warnings}
