"""Detect and normalize unique member identifiers."""

from __future__ import annotations

from typing import Any

_FIELD = "member_id"


def detect_member_id(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    raw_table: Any | None = None,
    column_index: int,
    header: str | None,
    column_values_sample: list[Any],
    column_values: list[Any],
    manifest: dict[str, Any] | None = None,
    logger,
    event_emitter,
    **_: Any,
) -> float:
    """
    Column detector: return a confidence score for the member ID column.

    logger → human-friendly logs
    event_emitter → structured run events (rarely needed for detectors)
    """
    sample_values = column_values_sample or []
    header_score = 0.0
    if header:
        lowered = header.strip().lower()
        if "member" in lowered and "id" in lowered:
            header_score = 0.9
        elif lowered in {"id", "member #", "member no", "member number"}:
            header_score = 0.7
        elif "id" in lowered:
            header_score = 0.5

    numeric_hits = sum(1 for value in sample_values if value is not None and str(value).strip().isdigit())
    sample_score = (numeric_hits / max(1, len(sample_values))) * 0.3
    score = round(min(1.0, header_score + sample_score), 2)

    logger.debug("member_id header=%r score=%.2f column=%s", header, score, column_index)
    return score


def transform(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    field_name: str,
    value: Any,
    row: dict[str, Any],
    field_config: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    logger,
    event_emitter,
    **_: Any,
) -> dict[str, Any] | None:
    """Normalize identifiers to trimmed uppercase strings."""

    if value in (None, ""):
        logger.warning("member_id missing at row=%s", row_index)
        event_emitter.custom("transform.member_id.missing", row_index=row_index)
        return {field_name: None}
    cleaned = str(value).strip()
    normalized = cleaned.upper() if cleaned else None
    return {field_name: normalized}


def validate(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    field_name: str,
    value: Any,
    row: dict[str, Any],
    field_config: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    logger,
    event_emitter,
    **_: Any,
) -> list[dict[str, Any]]:
    """Emit validation issues for missing identifiers."""

    issues: list[dict[str, Any]] = []
    required = bool(field_config and field_config.get("required"))

    if value in (None, "") and required:
        issues.append(
            {
                "code": "missing_required",
                "severity": "error",
                "message": f"{field_name.replace('_', ' ').title()} is required.",
            }
        )

    return issues
