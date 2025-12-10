from __future__ import annotations

from typing import Any, Dict

from ade_engine.registry.models import FieldDef


def register(registry):
    registry.register_field(FieldDef(name="middle_name", label="Middle Name", dtype="string", synonyms=["middle name", "mname", "middle initial"]))
    registry.register_column_detector(detect_middle_name_header, field="middle_name", priority=40)
    registry.register_column_detector(detect_middle_name_values, field="middle_name", priority=15)
    registry.register_column_transform(normalize_middle_name, field="middle_name", priority=0)
    registry.register_column_validator(validate_middle_name, field="middle_name", priority=0)


def detect_middle_name_header(
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
    header_lower = header_text.lower()
    if ("middle" in t and "name" in t) or "m.i" in header_lower:
        return {"middle_name": 1.0}
    if "mi" in t or "middle" in t:
        return {"middle_name": 0.8}
    return None


def detect_middle_name_values(
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
    initials = 0
    total = 0
    for v in values_sample:
        s = ("" if v is None else str(v)).strip()
        if not s:
            continue
        total += 1
        if len(s) == 1 or (len(s) == 2 and "." in s):
            initials += 1
    if total == 0:
        return None
    score = min(1.0, initials / total)
    return {"middle_name": score}


def normalize_middle_name(*, field_name, values, mapping, state, metadata, input_file_name, logger) -> list[Dict[str, Any]]:
    """Return `[{"row_index": int, "value": {"middle_name": ...}}, ...]`."""

    return [
        {
            "row_index": idx,
            "value": {
                "middle_name": (None if v is None else str(v).strip() or None),
            },
        }
        for idx, v in enumerate(values)
    ]


def validate_middle_name(*, field_name, values, mapping, state, metadata, column_index, input_file_name, logger) -> list[Dict[str, Any]]:
    """Return `[{"row_index": int, "message": str}, ...]` for failing cells."""

    issues: list[Dict[str, Any]] = []
    for idx, v in enumerate(values):
        s = "" if v is None else str(v).strip()
        if len(s) > 40:
            issues.append({
                "row_index": idx,
                "message": "Middle name too long",
            })
    return issues

# Example cell-level helpers (commented out):
# These run per cell; use column-level variants above when possible for speed and
# when populating multiple fields from one column.
#
# def normalize_middle_name_cell(value: object | None) -> Dict[str, Any]:
#     return {"row_index": 0, "value": {"middle_name": (None if value is None else str(value).strip() or None)}}
#
# def validate_middle_name_cell(value: object | None) -> Dict[str, Any] | None:
#     text_value = "" if value is None else str(value).strip()
#     if text_value and len(text_value) > 40:
#         return {"row_index": 0, "message": "Middle name too long"}
#     return None
