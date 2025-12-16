from __future__ import annotations

from typing import Any, Dict

from ade_engine.models import FieldDef


def register(registry):
    registry.register_field(FieldDef(name="first_name", label="First Name", dtype="string"))
    registry.register_column_detector(detect_first_name_header, field="first_name", priority=50)
    registry.register_column_detector(detect_first_name_values, field="first_name", priority=20)
    registry.register_column_transform(normalize_first_name, field="first_name", priority=0)
    registry.register_column_validator(validate_first_name, field="first_name", priority=0)


def detect_first_name_header(
    *,
    column_index,
    header,
    values,
    values_sample,
    sheet_name,
    metadata,
    state,
    input_file_name,
    logger,
) -> dict[str, float] | None:
    header_text = "" if header in (None, "") else str(header)
    header_tokens = set(header_text.lower().replace("-", " ").split())
    if not header_tokens:
        return None
    if "first" in header_tokens and "name" in header_tokens:
        return {"first_name": 1.0}
    if "fname" in header_tokens or "given" in header_tokens:
        return {"first_name": 0.9}
    return None


def detect_first_name_values(
    *,
    column_index,
    header,
    values,
    values_sample,
    sheet_name,
    metadata,
    state,
    input_file_name,
    logger,
) -> dict[str, float] | None:
    values_sample = values_sample or []
    if not values_sample:
        return None
    shortish = 0
    total = 0
    for v in values_sample:
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


def normalize_first_name(*, field_name, column, table, mapping, state, metadata, input_file_name, logger) -> list[Any]:
    return [(None if v is None else str(v).strip() or None) for v in column]


def validate_first_name(*, field_name, column, table, mapping, state, metadata, input_file_name, logger) -> list[Dict[str, Any]]:
    issues: list[Dict[str, Any]] = []
    for idx, v in enumerate(column):
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
