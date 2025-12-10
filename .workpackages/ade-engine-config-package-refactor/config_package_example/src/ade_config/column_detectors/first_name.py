from __future__ import annotations

from typing import Any, Dict

from ade_engine.registry.models import ColumnDetectorContext, FieldDef, TransformContext, ValidateContext


def register(registry):
    registry.register_field(FieldDef(
        name="first_name",
        label="First Name",
        dtype="string",
        synonyms=["first name", "given name", "fname"],
    ))
    registry.register_column_detector(detect_first_name_header, field="first_name", priority=50)
    registry.register_column_detector(detect_first_name_values, field="first_name", priority=20)
    registry.register_column_transform(normalize_first_name, field="first_name", priority=0)
    registry.register_column_validator(validate_first_name, field="first_name", priority=0)


def detect_first_name_header(ctx: ColumnDetectorContext) -> dict[str, float] | None:
    header_text = "" if ctx.header in (None, "") else str(ctx.header)
    header_tokens = set(header_text.lower().replace("-", " ").split())
    if not header_tokens:
        return None
    if "first" in header_tokens and "name" in header_tokens:
        return {"first_name": 1.0}
    if "fname" in header_tokens or "given" in header_tokens:
        return {"first_name": 0.9}
    return None


def detect_first_name_values(ctx: ColumnDetectorContext) -> dict[str, float] | None:
    sample = ctx.sample or []
    if not sample:
        return None
    shortish = 0
    total = 0
    for v in sample:
        s = ("" if v is None else str(v)).strip()
        if not s:
            continue
        total += 1
        if 2 <= len(s) <= 20 and " " not in s:
            shortish += 1
    if total == 0:
        return None
    score = min(1.0, shortish / total)
    return {"first_name": score}


def normalize_first_name(ctx: TransformContext) -> list[Dict[str, Any]]:
    """Return `[{"row_index": int, "value": {"first_name": ...}}, ...]`."""

    return [
        {
            "row_index": idx,
            "value": {
                "first_name": (None if v is None else str(v).strip() or None),
            },
        }
        for idx, v in enumerate(ctx.values)
    ]


def validate_first_name(ctx: ValidateContext) -> list[Dict[str, Any]]:
    """Return `[{"row_index": int, "message": str}, ...]` for failed cells."""

    issues: list[Dict[str, Any]] = []
    for idx, v in enumerate(ctx.values):
        s = "" if v is None else str(v).strip()
        if s and len(s) > 50:
            issues.append({
                "row_index": idx,
                "message": "First name too long",
            })
    return issues

# Example cell-level helpers (commented out):
# These process a single cell at a time; prefer the column-level versions above
# when registering for better performance and when touching multiple fields.
#
# def normalize_first_name_cell(value: object | None) -> dict[str, Any]:
#     return {"row_index": 0, "value": {"first_name": (None if value is None else str(value).strip() or None)}}
#
# def validate_first_name_cell(value: object | None) -> dict[str, Any] | None:
#     text_value = "" if value is None else str(value).strip()
#     if text_value and len(text_value) > 50:
#         return {"row_index": 0, "message": "First name too long"}
#     return None
