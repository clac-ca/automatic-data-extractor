from __future__ import annotations

from typing import Any, Dict

from ade_engine.registry.models import FieldDef


def register(registry):
    registry.register_field(FieldDef(name="last_name", label="Last Name", dtype="string"))
    registry.register_column_detector(detect_last_name_header, field="last_name", priority=50)
    registry.register_column_detector(detect_last_name_values, field="last_name", priority=20)
    registry.register_column_transform(normalize_last_name, field="last_name", priority=0)
    registry.register_column_validator(validate_last_name, field="last_name", priority=0)


def detect_last_name_header(
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
    t = set(header_text.lower().replace("-", " ").split())
    if not t:
        return None
    if ("last" in t and "name" in t) or "surname" in t or "family" in t:
        return {"last_name": 1.0}
    if "lname" in t:
        return {"last_name": 0.9}
    return None


def detect_last_name_values(
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
    total = 0
    longish = 0
    for v in values_sample:
        s = ("" if v is None else str(v)).strip()
        if not s:
            continue
        total += 1
        if len(s) >= 2 and " " not in s:
            longish += 1
    if total == 0:
        return None
    score = min(1.0, longish / total)
    return {"last_name": score}


def normalize_last_name(*, field_name, column, table, mapping, state, metadata, input_file_name, logger) -> list[Any]:
    return [(None if v is None else str(v).strip() or None) for v in column]


def validate_last_name(*, field_name, column, table, mapping, state, metadata, input_file_name, logger) -> list[Dict[str, Any]]:
    issues: list[Dict[str, Any]] = []
    for idx, v in enumerate(column):
        s = "" if v is None else str(v).strip()
        if s and len(s) > 80:
            issues.append({
                "row_index": idx,
                "message": "Last name too long",
            })
    return issues

# Example cell-level helpers (commented out):
# These run one cell at a time; prefer column-level versions above for performance
# and when emitting multiple fields per column.
#
# def normalize_last_name_cell(value: object | None) -> Dict[str, Any]:
#     return {"row_index": 0, "value": {"last_name": (None if value is None else str(value).strip() or None)}}
#
# def validate_last_name_cell(value: object | None) -> Dict[str, Any] | None:
#     text_value = "" if value is None else str(value).strip()
#     if text_value and len(text_value) > 80:
#         return {"row_index": 0, "message": "Last name too long"}
#     return None
