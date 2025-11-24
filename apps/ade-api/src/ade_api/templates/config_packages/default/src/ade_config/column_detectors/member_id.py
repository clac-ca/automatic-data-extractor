"""Detect and normalize unique member identifiers."""

from __future__ import annotations

from typing import Any

_FIELD = "member_id"


def detect_member_id(
    *,
    header: str | None,
    column_values_sample: list[Any],
    **_: Any,
) -> float:
    """Return a confidence score for the member ID column."""
    header_score = 0.0
    if header:
        lowered = header.strip().lower()
        if "member" in lowered and "id" in lowered:
            header_score = 0.9
        elif lowered in {"id", "member #", "member no", "member number"}:
            header_score = 0.7
        elif "id" in lowered:
            header_score = 0.5

    numeric_hits = sum(
        1 for value in column_values_sample
        if value is not None and str(value).strip().isdigit()
    )
    sample_score = (numeric_hits / max(1, len(column_values_sample))) * 0.3
    score = round(min(1.0, header_score + sample_score), 2)

    return score


def transform(
    *,
    value: Any,
    field_name: str = _FIELD,
    **_: Any,
) -> dict[str, Any] | None:
    """Normalize identifiers to trimmed uppercase strings."""
    if value in (None, ""):
        return {field_name: None}
    cleaned = str(value).strip()
    normalized = cleaned.upper() if cleaned else None
    return {field_name: normalized}


def validate(
    *,
    value: Any,
    field_name: str = _FIELD,
    field_meta: dict[str, Any] | None = None,
    **_: Any,
) -> list[dict[str, Any]]:
    """Return validation issues for missing identifiers."""
    issues: list[dict[str, Any]] = []
    required = bool(field_meta and field_meta.get("required"))

    if value in (None, "") and required:
        issues.append(
            {
                "code": "missing_required",
                "severity": "error",
                "message": f"{field_name.replace('_', ' ').title()} is required."
            }
        )

    return issues
